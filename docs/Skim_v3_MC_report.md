# Skim v3 MC report example

This is the report produced for the following Run 3 MC skim:

```text
/eos/cms/store/group/phys_higgs/cmshmm/vdamante/skim_v3/Run3_2022/VBFHto2Mu_M125_powheg/report_1.json
```

It contains the event cutflow and the generator, pileup, and QCD-scale weight sums.

```json
{
  "Initial": 25168,
  "MET_filters": {
    "pass": 25152
  },
  "Trigger_matching_for_singleMu": {
    "pass": 22602
  },
  "Exactly_2_muons": {
    "pass": 16693
  },
  "dimuon_mass_cut": {
    "pass": 16686
  },
  "No_extra_electrons": {
    "pass": 16681
  },
  "gen": {
    "total": {
      "selection": "return true;",
      "value": 105192.29367256165
    }
  },
  "pu": {
    "total": {
      "selection": "return true;",
      "value": 25175.60910387641,
      "value_unsigned": 25201.45585682607
    }
  },
  "pu_up": {
    "total": {
      "selection": "return true;",
      "value_unsigned": 25182.738815212942,
      "value": 25157.086202602237
    }
  },
  "pu_down": {
    "total": {
      "selection": "return true;",
      "value_unsigned": 25224.2816579535,
      "value": 25197.671309292506
    }
  },
  "gen_qcdScale_muR0p5_muF0p5": {
    "total": {
      "selection": "return true;",
      "value": 104659.22822454572
    }
  },
  "pu_qcdScale_muR0p5_muF0p5": {
    "total": {
      "selection": "return true;",
      "value": 25047.370181371323,
      "value_unsigned": 25096.754651146624
    }
  },
  "gen_qcdScale_muR0p5_muF1": {
    "total": {
      "selection": "return true;",
      "value": 104895.86579442024
    }
  },
  "pu_qcdScale_muR0p5_muF1": {
    "total": {
      "selection": "return true;",
      "value": 25104.397990055266,
      "value_unsigned": 25147.020420921508
    }
  },
  "gen_qcdScale_muR1_muF0p5": {
    "total": {
      "selection": "return true;",
      "value": 105168.1032449007
    }
  },
  "pu_qcdScale_muR1_muF0p5": {
    "total": {
      "selection": "return true;",
      "value": 25169.413821833197,
      "value_unsigned": 25201.244103386074
    }
  },
  "gen_qcdScale_muR1_muF2": {
    "total": {
      "selection": "return true;",
      "value": 105743.31619465351
    }
  },
  "pu_qcdScale_muR1_muF2": {
    "total": {
      "selection": "return true;",
      "value": 25307.814209547254,
      "value_unsigned": 25327.836139135106
    }
  },
  "gen_qcdScale_muR2_muF1": {
    "total": {
      "selection": "return true;",
      "value": 105430.62114560604
    }
  },
  "pu_qcdScale_muR2_muF1": {
    "total": {
      "selection": "return true;",
      "value": 25232.863991770475,
      "value_unsigned": 25245.216581127395
    }
  },
  "gen_qcdScale_muR2_muF2": {
    "total": {
      "selection": "return true;",
      "value": 105733.75896900147
    }
  },
  "pu_qcdScale_muR2_muF2": {
    "total": {
      "selection": "return true;",
      "value": 25305.6856731422,
      "value_unsigned": 25312.897367604328
    }
  }
}
```
