# Interfaccia semplice del framework H→μμ

`hmumu` è l'entry point consigliato per le operazioni quotidiane. Nasconde i
wrapper Bash, la separazione delle opzioni con `--` e la scelta tra produzione
centrale e sistematiche.

Per sicurezza, i comandi di produzione mostrano soltanto il piano. Aggiungere
`--run` per eseguirlo.

## Produrre un solo istogramma

```bash
./hmumu hist \
  --era 2025 \
  --dataset DYto2Mu_MLL_105to160_amcatnloFXFX \
  --variable m_mumu \
  --region Signal_Fit \
  --category VBF \
  --local
```

Il comando sopra stampa il comando effettivo. Per eseguirlo:

```bash
./hmumu hist \
  -e 2025 \
  -d DYto2Mu_MLL_105to160_amcatnloFXFX \
  -v m_mumu \
  -r Signal_Fit \
  -c VBF \
  --local \
  --run
```

### Test rapido su un solo file

```bash
./hmumu hist \
  -e 2025 \
  -d DYto2Mu_MLL_105to160_amcatnloFXFX \
  -v m_mumu \
  -r Z_sideband \
  -c ggF \
  --one-file \
  --run
```

`--one-file` equivale a `--max-files 1`. Per provarne più di uno:

```bash
./hmumu hist ... --max-files 3 --run
```

La selezione usa i primi file validi del manifest. La normalizzazione continua
a usare i metadati completi del dataset, ma il risultato non rappresenta lo
yield completo.

Per evitare di confondere test parziali con produzioni ufficiali, la CLI scrive
automaticamente sotto:

```text
/tmp/vdamante/hmumu_tests/Hists_<SYSTEMATIC>/
```

Un `--output-dir` esplicito ha precedenza.

## Produrre una campagna

Più valori possono essere separati da virgole oppure ripetuti:

```bash
./hmumu hist \
  -e 2022,2022EE,2023,2023BPix,2024,2025 \
  -s Central,JERC,ScaRe,Muon,PU,QCDScale,PDF \
  -r Signal_Fit,Z_sideband \
  -c VBF \
  --condor \
  --run
```

I gruppi di dataset predefiniti includono `data` soltanto per `Central`. Per
selezionare esplicitamente i gruppi:

```bash
./hmumu hist -e 2025 \
  --datasets DY_amcatnlo_105_160,signals \
  -v DNN_NNOutput -r Signal_Fit -c VBF
```

## Componenti DY hard/PU per il fit dei jet

La modalità dedicata:

```bash
./hmumu hist \
  -e 2025 \
  --datasets DY_amcatnlo,DY_amcatnlo_105_160 \
  -r Z_sideband \
  --dy-jet-components \
  --local
```

produce componenti esclusivi:

```text
ggF_0J_Hard
ggF_1J_Hard  ggF_1J_PU
ggF_2J_Hard  ggF_2J_PU1  ggF_2J_PU2
VBF_Hard     VBF_PU1     VBF_PU2
```

Un jet è `Hard` quando `genJetIdx >= 0` e `PU` quando `genJetIdx < 0`.
Per ggF vengono prenotati automaticamente i template prescritti:

| Molteplicità reco | Template |
|---|---|
| 0J | `m_mumu` |
| 1J | TH2 `leadingjet_eta` × `leadingjet_pt` |
| ≥2J | TH2 `subleadingjet_eta` × `subleadingjet_pt` |

Il conteggio ggF usa i primi due jet reco ordinati in pT. Il conteggio VBF usa
invece esattamente `VBFJetIdx_1` e `VBFJetIdx_2`.

Per VBF, `-v` sceglie la variabile da produrre; il default è `m_mumu`:

```bash
./hmumu hist -e 2025 --datasets DY_amcatnlo_105_160 \
  -r Signal_Fit -v DNN_NNOutput --dy-jet-components
```

Questa modalità deve essere usata su una produzione dedicata ai dataset DY,
non insieme a data o ad altri processi. Aggiungere `--run` dopo aver controllato
il piano.

Gli skim devono contenere `SelectedJet_genJetIdx` oppure `Jet_genJetIdx`.
Gli skim `skim_v2` controllati durante lo sviluppo non contengono ancora queste
colonne e devono essere rigenerati con la versione corrente di
`analysis/jets.py`.

Le opzioni più usate sono visibili con:

```bash
./hmumu hist --help
```

Opzioni avanzate di `hist_maker.py` possono ancora essere inoltrate alla fine:

```bash
./hmumu hist -e 2025 -d GluGluHto2Mu -v m_mumu \
  -- --no-skip-failed-chunks
```

### Gestione dei chunk MC falliti

La policy predefinita è:

```text
MC con --n-cores 1  → skip e rinormalizzazione
data                 → fail-fast
MC parallelo         → fail-fast
```

Quando un chunk MC seriale fallisce:

1. tutti i file contenuti nel chunk vengono esclusi;
2. i rispettivi report JSON vengono esclusi dal calcolo dei denominatori;
3. i denominatori Central e QCD-scale vengono ricalcolati;
4. tutti i chunk sopravvissuti vengono processati nuovamente;
5. soltanto i nuovi temporanei correttamente normalizzati vengono uniti.

Sui dati un errore interrompe sempre la produzione. La modalità skip non può
essere combinata con `--resume`, perché i temporanei esistenti potrebbero
contenere una normalizzazione differente.

```bash
./hmumu hist -e 2025 -d DYto2Mu_M_50_amcatnloFXFX \
  -v m_mumu -r Z_sideband -c ggF --run
```

Per forzare il fail-fast anche su MC:

```bash
./hmumu hist ... --run -- --no-skip-failed-chunks
```

## Campagna DY jet components Central

La campagna preparata per tutte le ere è:

```bash
campaigns/run3_dy_jet_components_central.sh
```

Senza argomenti stampa le sei submission senza lanciarle. Per eseguire il
preflight degli skim e inviare i job:

```bash
campaigns/run3_dy_jet_components_central.sh --run
```

Copre 2022, 2022EE, 2023, 2023BPix, 2024 e 2025, usa i gruppi
`DY_amcatnlo,DY_amcatnlo_105_160`, le regioni `Signal_Fit`, `H_sideband` e
`Z_sideband`, e scrive in:

```text
/eos/user/v/vdamante/H_mumu/Hists_DYJetComponents_Central
```

Prima della submission verifica per ogni dataset che gli skim contengano
`SelectedJet_genJetIdx` oppure `Jet_genJetIdx`.

## Trovare una variabile

```bash
./hmumu where m_mumu
./hmumu where DNN_NNOutput
./hmumu where weight_pu_up
```

Il comando mostra:

1. la funzione che produce la colonna con `Define`/`Redefine`;
2. l'espressione usata e gli input conosciuti;
3. le configurazioni YAML/TOML;
4. gli altri riferimenti nel codice.

Riconosce anche molti nomi costruiti dinamicamente con f-string. Per vedere
l'indice delle colonne scoperte staticamente:

```bash
./hmumu vars
./hmumu vars m_mumu
./hmumu vars weight --dynamic
```

`--dynamic` include template come `mu{...}_pt`. La ricerca non può ricostruire
ogni nome generato a runtime, ma in quel caso indica la funzione produttrice.

## Controllare l'ambiente

```bash
./hmumu doctor
```

## Compatibilità

Gli script `histograms/scripts/hists.sh` e
`histograms/scripts/systematics.sh` restano funzionanti. `hmumu` costruisce gli
stessi job e consente quindi una migrazione graduale dei vecchi script.

## Regola per nuovo codice

- Comandi destinati agli utenti: aggiungerli a `hmumu`.
- Cataloghi e configurazioni: mantenerli dichiarativi in `config/`.
- Trasformazioni del dataframe: una funzione con uno scopo e un nome descrittivo.
- Orchestrazione locale/Condor: non duplicare la costruzione del job.
- I wrapper Bash preesistenti sono compatibilità, non nuovi entry point.
