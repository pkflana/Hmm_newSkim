# Architettura e direzione di semplificazione

## Flusso attuale

La produzione di istogrammi attraversa questi livelli:

```text
comando utente
  → hists.sh / systematics.sh
    → common/scripts/dataset_campaign.sh
      → esecuzione locale oppure file jobs.tsv
        → htcondor/run_stage_condor.sh
          → histograms/hist_maker.py
```

Il calcolo delle colonne attraversa invece:

```text
NanoAOD
  → analysis/skim.py
    → corrections/*
    → analysis/muons.py, analysis/jets.py, analysis/other.py
  → skim ROOT
    → common/add_vars_to_skim_tuples.py
    → common/histogram_pipeline.py
    → histograms/hist_maker.py
```

Le configurazioni dipendenti dall'era si trovano in `config/Run3_*/`. Le
variabili da istogrammare sono principalmente in `maincfg.yaml`; selezioni e
sistematiche sono rispettivamente in `selections.yaml` e `systematics.yaml`.

## Problemi osservati

- Le opzioni sono divise tra il parser della campagna e quello del maker tramite
  un separatore `--` non intuitivo.
- Locale e Condor costruiscono separatamente comandi quasi identici.
- `dataset_campaign.sh` combina catalogo dataset, policy, parsing CLI,
  monitoraggio e generazione Condor in un solo file.
- `hist_maker.py` combina parsing, validazione input, costruzione dataframe,
  multiprocessing, scrittura temporanei e merge.
- Le colonne non hanno metadati comuni su origine e dipendenze; molte sono
  costruite dinamicamente.
- Script personali duplicano matrici di ere, regioni e sistematiche.

## Strategia incrementale

1. Usare `hmumu` come unica interfaccia pubblica per gli istogrammi e per
   navigare le colonne.
2. Spostare progressivamente il catalogo dei dataset dal Bash a dati
   dichiarativi, mantenendo invariati i nomi dei gruppi.
3. Estrarre dal maker oggetti Python separati per configurazione, pianificazione
   dei chunk ed esecuzione.
4. Fare usare a locale e Condor lo stesso oggetto di job serializzato, invece di
   ricostruire la CLI.
5. Introdurre un registro di colonne con nome, produttore, espressione e
   dipendenze; `hmumu where` è il primo strato di compatibilità mentre il
   registro viene popolato.
6. Deprecare i wrapper solo dopo confronto degli output ROOT su campioni
   rappresentativi.

Questa sequenza riduce subito la complessità percepita senza cambiare in un
unico passaggio il codice fisico già validato.

## Confini da mantenere

```text
tools/hmumu.py                 interfaccia e richieste dell'utente
common/variable_catalog.py     indice statico delle colonne
common/scripts/                compatibilità e orchestrazione legacy
common/histogram_pipeline.py   trasformazioni condivise del dataframe
histograms/hist_maker.py       esecuzione ROOT, chunk e scrittura
config/                        dataset, selezioni, variabili e sistematiche
```

La logica fisica non deve entrare nella CLI o negli script Condor. Allo stesso
modo, `hist_maker.py` non dovrebbe acquisire nuovi cataloghi di dataset o policy
di campagna.

## Debito ancora presente

`dataset_campaign.sh` e `hist_maker.py` rimangono grandi. Sono mantenuti come
backend stabile mentre l'interfaccia viene semplificata. I prossimi tagli sicuri
sono:

1. un job serializzato unico condiviso da locale e Condor;
2. catalogo dataset dichiarativo per era;
3. estrazione da `hist_maker.py` di configurazione, piano chunk e merge;
4. registro esplicito delle dipendenze delle colonne.

Questi cambi richiedono confronti numerici degli output ROOT; non vanno
mescolati a modifiche della selezione o delle correzioni.
