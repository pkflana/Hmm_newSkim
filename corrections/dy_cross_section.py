import math
import yaml
import os

# =====================================================================
# CLASSE DATABASE SEZIONI D'URTO (Risoluzione Formule Stringa)
# =====================================================================
class MiniCrossSectionDB:
    def __init__(self, xs_cfg_dict):
        """Inizializza il database partendo dal dizionario globale delle sezioni d'urto."""
        self.entries = {}
        self.values = {}

        # Carica tutte le voci disponibili dal file crossSections globale
        for key, entry in xs_cfg_dict.items():
            if isinstance(entry, dict):
                if "crossSec" in entry:
                    self.add_entry(key, entry["crossSec"])
                elif "BR" in entry:
                    self.add_entry(key, entry["BR"])

    def add_entry(self, name, expr):
        """Aggiunge dinamicamente una nuova voce valutando l'espressione ricorsivamente."""
        if name in self.values:
            return
        value = self.evaluate_expression(expr, name)
        self.values[name] = value

    def get_value(self, name):
        """Restituisce il valore numerico associato a una chiave."""
        if name not in self.values:
            raise RuntimeError(f"MiniCrossSectionDB: Chiave sconosciuta nel database: '{name}'")
        return self.values[name]

    def evaluate_expression(self, expr, name=None):
        """Risolve stringhe e formule matematiche complesse (es. A - B - C) usando eval."""
        try:
            if isinstance(expr, (int, float)):
                return float(expr)
            elif isinstance(expr, str):
                # Usa self.values come contesto globale per risolvere i nomi delle cross-section
                result = eval(expr, {}, self.values)
            else:
                raise RuntimeError(f"Tipo di espressione non valido: {type(expr)}")

            if not isinstance(result, float):
                raise RuntimeError("L'espressione non ha prodotto un valore di tipo float")
            if math.isnan(result) or math.isinf(result):
                raise RuntimeError("L'espressione ha prodotto un valore non fisico (NaN o Inf)")
            if result < 0:
                raise RuntimeError(f"L'espressione ha prodotto un valore negativo: {result}")

            return result
        except Exception as e:
            msg = f"'{expr}'" + (f" per la voce '{name}'" if name else "")
            raise RuntimeError(f"CrossSectionDB: Errore nella valutazione di {msg}: {e}")


# =====================================================================
# FUNZIONI DI CALCOLO E APPLICAZIONE (Adattate allo YAML a stringhe lunghe)
# =====================================================================

def dy_cross_section_calc(db, dysf_cfg):
    """
    Calcola i fattori di cross-section interpretando la struttura dello YAML.
    Nessun valore hardcoded. Se totalCrossSection è assente/commentata, il check salta.
    """
    # 1. Gestione dinamica di totalCrossSectionScaling (Es: "DY_NNLO_QCD_NLO_EW / DYto2L_...")
    scaling_expr = dysf_cfg['totalCrossSectionScaling']

    if isinstance(scaling_expr, str) and '/' in scaling_expr:
        # Dividiamo la stringa sui due lati dello slash '/'
        numer_key, denom_key = [k.strip() for k in scaling_expr.split('/')]
        numer_val = db.get_value(numer_key)
        denom_val = db.get_value(denom_key)
        total_xs_scaling = numer_val / denom_val
    else:
        # Se fosse una stringa senza slash o già un numero float
        total_xs_scaling = db.evaluate_expression(scaling_expr, name="totalCrossSectionScaling")

    # 2. Calcolo delle sezioni d'urto bin per bin valutando le stringhe dello YAML (formule con il meno '-')
    selection_bins = []
    for bin_entry in dysf_cfg['bins']:
        raw_xs = bin_entry['crossSection']

        if isinstance(raw_xs, str):
            # Valuta l'intera stringa aritmetica sfruttando il DB
            subtotal = db.evaluate_expression(raw_xs, name=bin_entry['name'])
        elif isinstance(raw_xs, dict):
            # Fallback se in futuro rimetti il formato add/subtract
            subtotal = 0.0
            for entry in raw_xs.get('add', []): subtotal += db.get_value(entry)
            for entry in raw_xs.get('subtract', []): subtotal -= db.get_value(entry)
        else:
            subtotal = float(raw_xs)

        selection_bins.append(subtotal)

    # 3. Controllo di coerenza (Sanity Check) - Eseguito SOLO se la chiave esiste e non è commentata
    total_xs_from_bins = sum(selection_bins)
    expected_key = dysf_cfg.get('totalCrossSection', None) # Restituisce None se è commentata o assente

    if expected_key:
        expected_total_xs = db.get_value(expected_key)
        diff = abs(total_xs_from_bins - expected_total_xs) / expected_total_xs

        print(f"[MCStitcher-Core] Somma dei bin calcolata: {total_xs_from_bins}")
        print(f"[MCStitcher-Core] Sezione d'urto attesa per il controllo: {expected_total_xs}")
        print(f"[MCStitcher-Core] Differenza relativa: {diff}")

        if diff > 0.001:
            raise RuntimeError(
                f"MCStitcher Error: sum of bin cross-sections ({total_xs_from_bins}) "
                f"does not match total cross-section ({expected_total_xs}) for key '{expected_key}'. Diff: {diff}"
            )
    else:
        # Questo è esattamente ciò che serve per sbloccarti con lo YAML attuale!
        print(f"[MCStitcher-Core] 'totalCrossSection' non definita nello YAML (omessa o commentata).")
        print(f"[MCStitcher-Core] Controllo saltato. Somma totale dei bin utilizzata: {total_xs_from_bins}")

    return total_xs_scaling, selection_bins

def apply_dy_cross_section(df, weight_xs_name, xs_cfg, dysf_cfg, json_dict):
    """
    Redefinisce il ramo della sezione d'urto nell'RDataFrame usando il DB interno.
    Sintassi C++ corretta per evitare errori di cattura implicit lambda in Cling.
    """
    # Inizializziamo il database MiniCrossSectionDB con il dizionario globale delle sezioni d'urto
    db = MiniCrossSectionDB(xs_cfg)

    # Se nello YAML dello stitching ci sono definizioni locali extra (crossSections: {}), le carichiamo nel DB
    if "crossSections" in dysf_cfg and dysf_cfg["crossSections"]:
        for entry_name, entry_expr in dysf_cfg["crossSections"].items():
            db.add_entry(entry_name, entry_expr)

    # Calcoliamo lo scaling e le sezioni d'urto binnate
    total_xs_scaling, selection_bins = dy_cross_section_calc(db, dysf_cfg)

    # Prepara le strutture per memorizzare i contatori dei pesi nel json_dict
    if 'gen' not in json_dict: json_dict['gen'] = {}
    if 'pu' not in json_dict: json_dict['pu'] = {}
    available_columns = [str(col) for col in df.GetColumnNames()]

    xs_expr_list = []
    columns_to_pass = set()

    for entry, binned_xs in zip(dysf_cfg['bins'], selection_bins):
        bin_name = entry['name']
        selection = entry['selection']

        # Estraiamo i nomi delle colonne usate nella selezione per passarle a Define (es: LHE_NpNLO)
        # Un trucco semplice: isoliamo i token alfabetici che corrispondono a colonne reali del DF
        for col in available_columns:
            if col in selection:
                columns_to_pass.add(col)

        # Registra i puntatori ResultPtr di RDataFrame per i yield
        if bin_name not in json_dict['gen']: json_dict['gen'][bin_name] = {}
        json_dict['gen'][bin_name]['selection'] = selection
        json_dict['gen'][bin_name]['value'] = df.Filter(selection).Sum("genWeight")

        if bin_name not in json_dict['pu']: json_dict['pu'][bin_name] = {}
        json_dict['pu'][bin_name]['selection'] = selection
        json_dict['pu'][bin_name]['value'] = df.Filter(selection).Sum("weight_pu")

        # Gestione variazioni sistematiche PU (Up/Down)
        for scale in ['up', 'down']:
            pu_var_name = f"weight_pu_{scale}"
            if pu_var_name not in available_columns: continue
            json_key = f"pu_{scale}"
            if json_key not in json_dict: json_dict[json_key] = {}
            if bin_name not in json_dict[json_key]: json_dict[json_key][bin_name] = {}
            json_dict[json_key][bin_name]['selection'] = selection
            json_dict[json_key][bin_name]['value'] = df.Filter(pu_var_name)

        # Calcola la cross-section finale scalata per questo bin (xs_scaling_globale * bin_xs)
        xs = total_xs_scaling * binned_xs
        sub_expr = f"if ({selection}) return float({xs});"
        xs_expr_list.append(sub_expr)

    xs_expr_list.append('throw std::runtime_error("No bin matched in DY cross-sectioning bins.");')

    # Costruiamo il macro blocco C++ puro senza annidarlo in una seconda lambda instanziata
    macro_xs_expr = "\n".join(xs_expr_list)

    # Convertiamo il set di colonne in una lista per passarla formalmente a Define
    columns_list = list(columns_to_pass)

    # Applica la trasformazione all'RDataFrame passando esplicitamente le colonne necessarie
    df = df.Define(weight_xs_name, macro_xs_expr, columns_list)

    return df, json_dict
# def dy_cross_section_calc(xs_cfg, dysf_cfg):
#     """
#     Calculates the new DY cross section factors for using multiple DY samples.
#     Args:
#     - xs_cfg expected to crossSections13p6TeV.yaml loaded as dict.
#     - dysf_cfg expected to be dy_cross_section_stitching.yaml loaded as dict.
#     Returns:
#     - The overall scale factor
#     - The selection-by-selection factors for different binnings
#     """
#     # Calculate the total cross-section scaling factor
#     numer = dysf_cfg['totalCrossSectionScaling']['numerator']
#     denom = dysf_cfg['totalCrossSectionScaling']['denominator']
#     numer = xs_cfg[numer]['crossSec']
#     denom = xs_cfg[denom]['crossSec']
#     if isinstance(numer, str):
#         numer = eval(numer)
#     if isinstance(denom, str):
#         denom = eval(denom)
#     total_xs_scaling = numer/denom

#     # Calculate the selection by selection cross-sections
#     selection_bins = []
#     for bin in dysf_cfg['bins']:
#         subtotal = 0
#         for entry in bin['crossSection']['add']:
#             subtotal += xs_cfg[entry]['crossSec']
#         for entry in bin['crossSection']['subtract']:
#             subtotal -= xs_cfg[entry]['crossSec']
#         selection_bins.append(subtotal)

#     # Check the factor
#     total_xs_from_bins = sum(selection_bins)
#     expected_total_xs = dysf_cfg['totalCrossSectionScaling']['numerator']
#     expected_total_xs = xs_cfg[expected_total_xs]['crossSec']
#     diff = abs(total_xs_from_bins - expected_total_xs)/expected_total_xs
#     print(expected_total_xs)
#     print(total_xs_from_bins)
#     print(diff)
#     assert diff < 0.001

#     return total_xs_scaling, selection_bins


# def apply_dy_cross_section(df, weight_xs_name, xs_cfg, dysf_cfg, json_dict):
#     """
#     Redefines the weight_xs branch for DY samples.
#     Args:
#     - df is the working RDataFrame
#     - xs_cfg expected to crossSections13p6TeV.yaml loaded as dict.
#     - dysf_cfg_path is the .yaml file containing the DY stitching configuration
#     Returns:
#     - The updated RDataFrame
#     """
#     # Get needed values from dy_cross_section_calc.
#     total_xs_scaling, selection_bins = dy_cross_section_calc(xs_cfg, dysf_cfg)
#     # Build the RDataFrame expression to assign new cross-section values
#     xs_expr_list = []
#     for entry, binned_xs in zip(dysf_cfg['bins'], selection_bins):
#         ### sum of gen weigths
#         if 'gen' not in json_dict.keys():
#             json_dict['gen'] = {}
#         if entry['name'] not in json_dict['gen'].keys():
#             json_dict['gen'][entry['name']] = {}
#         json_dict['gen'][entry['name']]['selection'] = entry['selection']
#         json_dict['gen'][entry['name']]['value'] = df.Filter(entry['selection']).Sum("genWeight")
#         ### sum of pu weights

#         if entry['name'] not in json_dict['pu'].keys():
#             json_dict['pu'][entry['name']] = {}
#         json_dict['pu'][entry['name']]['selection'] = entry['selection']
#         json_dict['pu'][entry['name']]['value'] = df.Filter(entry['selection']).Sum("weight_pu")
#         for scale in ['up','down']:
#             if f"weight_pu_{scale}" not in df.GetColumnNames(): continue
#             if entry['name'] not in json_dict[f"pu_{scale}"].keys():
#                 json_dict[f"pu_{scale}"][entry['name']] = {}
#             json_dict[f"pu_{scale}"][entry['name']]['selection'] = entry['selection']
#             json_dict[f"pu_{scale}"][entry['name']]['value'] = df.Filter(entry['selection']).Sum(f"weight_pu_{scale}")

#         xs = total_xs_scaling * binned_xs
#         selection = entry['selection']
#         sub_expr = f"if ({selection}) return {xs};"
#         xs_expr_list.append(sub_expr)
#     xs_expr_list.append('throw std::runtime_error("No bin matched in DY cross-sectioning bins.")')
#     xs_expr = "\n".join(xs_expr_list)

#     # Apply and return!
#     df = df.Define(weight_xs_name, xs_expr)


#     return df,json_dict
