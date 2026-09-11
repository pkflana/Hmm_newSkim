# Codice condiviso

`utilities.py` è l'unico modulo di utilities per skim, validazione,
istogrammi, plotting e campagne. Le funzioni sono raggruppate in sezioni:

- configurazione, selezione dei dataset e routing delle regioni;
- file, report dello skim, normalizzazione e suddivisione degli input;
- validazione dei file e lettura/scrittura dei manifest;
- inizializzazione ROOT e definizione delle colonne;
- modelli degli istogrammi, binning, rebinning e controllo dei contenuti.

ROOT e NumPy vengono importati dalle sole funzioni che li utilizzano.
Le operazioni di configurazione e submit non richiedono ROOT.
`list_root_files` restituisce i percorsi nel formato dell'input;
`discover_root_files` restituisce percorsi assoluti per la validazione.

La preparazione generica degli RDataFrame è in `common/prepare_rdf.py`, condivisa
da istogrammi, tuple di training, minituple e snapshot:

- `GetRdfForDataset` apre gli input e conserva le TChain per gli event loop lazy;
- `build_rdf` definisce osservabili e pesi di base;
- `prepare_rdf` applica in ordine variazioni, selezioni, correzioni finali e split;
- `prepare_region_dataframes` crea le viste per regione e categoria.

Il modulo accorpa tutta la preparazione dei precedenti `rdf_utilities`,
`prepare_rdf` e `histogram_rdf`. Gli helper di file e binning del vecchio
`rdf_utilities` sono invece in `common.utilities`.

Un esempio per esportare una minitupla da uno skim già prodotto:

```python
from common.prepare_rdf import prepare_rdf
from common.utilities import get_config, get_segmentation_dict, initialize_root_runtime

initialize_root_runtime()
era = "Run3_2025"
nodes = prepare_rdf(
    input_files=["skim_0.root"],
    dataset_name="EWK_2L2J_MLL50_MJJ120_herwig_Flashsim_New",
    era=era,
    selections_cfg=get_config(f"config/{era}/selections.yaml"),
    systematics_cfg=get_config(f"config/{era}/systematics.yaml"),
    seg_dict=get_segmentation_dict(["report_0.json"]),
)
rdf = nodes["inclusive"]
columns = ["m_mumu", "pt_mumu", "weight__Central"]
rdf.Snapshot("Events", "minituple.root", columns)
# In alternativa, per costruire un dataset di training:
# arrays = rdf.AsNumpy(columns)
```

Per MC, passare i report dell'intero dataset per la normalizzazione, anche
quando si elabora solo una parte dei file. L'esempio rappresenta un dataset
con un solo file. Le selezioni sono colonne booleane: `inclusive` non applica
automaticamente una regione finale. Usare `rdf.Filter(...)` oppure
`prepare_region_dataframes` per scegliere la stessa regione degli istogrammi.
Gli input sono le ntuple di skim dell'analisi, non NanoAOD ancora da skimmare.

`trigger_weights.py` e `jer_split.py` sono trasformazioni fisiche condivise,
come `add_vars.py`, `apply_custom_weights.py` e `jet_component_splitting.py`.
Restano moduli dedicati per tenere separati algoritmi diversi dalle utilities.
`HistHelper.h` è un header legacy spostato da `histograms`; la produzione
attuale non lo include e continua a usare `analysis/AnalysisTools.h`.

Il motore delle campagne è `campaigns/workflow.py`. Si usa dagli script shell
di `campaigns`, che passano azioni e opzioni a `campaigns/submit_campaign.sh`:

```sh
sh campaigns/dnn_vbf_z.sh --help
sh campaigns/dnn_vbf_z.sh paths --eras 2025 --mode central
```

Il motore Python gestisce submit, controllo di completezza, merge e plotting,
con le dipendenze tra gli stadi. Le configurazioni e gli entry point restano
shell; non è necessario invocare direttamente Python.
