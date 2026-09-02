# DY reweighting

This page summarizes the data-driven corrections applied to the Drell--Yan
(DY) simulation. The payloads documented here are the `Aug31` payloads selected
in the era-dependent `process_names.yaml` files.

## Available eras

The corrections are derived for four statistically combined period groups:

| Payload era | Applied to |
|---|---|
| `Run3_2022_2022EE` | 2022 and 2022EE |
| `Run3_2023_2023BPix` | 2023 and 2023BPix |
| `Run3_2024` | 2024 |
| `Run3_2025` | 2025 |

All three derivations use the Z sideband in data. The non-DY prediction is
subtracted before forming or fitting the DY correction. Depending on the
available process files, the subtraction includes EWK, single-top, single-H,
top-pair, ttX, tW, diboson, triboson and W+jets backgrounds.

## DY 0/1/2J component reweighting

### Method

- **Purpose:** correct the relative normalization of DY hard-scatter and
  pileup-jet components.
- **Inputs:** separate DY templates for `0J`, `1J_Hard`, `1J_PU`, `2J_Hard`,
  `2J_PU1` and `2J_PU2`, plus data and non-DY simulation.
- **ggF control region:** `Z_sideband_ggF`.
- **Fit model:** binned Poisson likelihood. The DY template normalizations are
  constrained to be non-negative; MC template statistical uncertainties are
  not nuisance parameters in the likelihood.
- **Sequential fit order:**
    1. fit `2JHard`, `2JPU1` and `2JPU2` in
       `eta_signed_vs_pt_subleadingjet`;
    2. keep the fitted 2J components fixed, then fit `1JHard` and `1JPU` in
       `eta_signed_vs_pt_leadingjet`;
    3. keep the fitted 2J and 1J components fixed, then fit the inclusive `0J`
       normalization in `m_mumu`.
- **VBF control region:** an independent three-parameter fit is performed in
  `Z_sideband_VBF` using `eta_signed_vs_pt_vbfjet1`. The fitted components are
  `VBFHard`, `VBFPU1` and `VBFPU2`, corresponding to two, one or zero hard
  reconstructed jets in the selected VBF pair.
- **Output:** one multiplicative normalization per exclusive component. An
  unmatched component receives the correctionlib default weight of `1.0`.
- **Uncertainty:** the quoted error is the square root of the corresponding
  diagonal element of the inverse-Hessian covariance matrix. Correlations
  between parameters fitted in the same stage are stored in
  `dy_012j_reweight_fit.json`.

### Fitted weights

Each entry is `weight +/- fit error`. More digits than normally needed are
shown so that the table can be compared directly with the payloads.

| Era | 0J | 1J Hard | 1J PU |
|---|---:|---:|---:|
| 2022 + 2022EE | 1.107251 +/- 0.000376 | 0.996037 +/- 0.000965 | 0.966518 +/- 0.009144 |
| 2023 + 2023BPix | 1.000000 +/- 0.000458 | 0.810823 +/- 0.001113 | 2.755697 +/- 0.012491 |
| 2024 | 1.035467 +/- 0.000227 | 1.041176 +/- 0.000526 | 1.000000 +/- 0.000968 |
| 2025 | 1.000000 +/- 0.000260 | 1.000000 +/- 0.000659 | 1.000000 +/- 0.001103 |

| Era | 2J Hard | 2J PU1 | 2J PU2 |
|---|---:|---:|---:|
| 2022 + 2022EE | 0.954060 +/- 0.002585 | 0.797728 +/- 0.009362 | 0.000000 +/- 0.030966 |
| 2023 + 2023BPix | 1.013560 +/- 0.003798 | 1.473842 +/- 0.012276 | 0.000000 +/- 0.039885 |
| 2024 | 0.900000 +/- 0.000851 | 0.900000 +/- 0.003433 | 0.900000 +/- 0.004270 |
| 2025 | 1.000000 +/- 0.001084 | 1.000000 +/- 0.004471 | 1.000000 +/- 0.005242 |

| Era | VBF Hard | VBF PU1 | VBF PU2 |
|---|---:|---:|---:|
| 2022 + 2022EE | 0.805706 +/- 0.010491 | 0.658459 +/- 0.014573 | 1.772066 +/- 0.103245 |
| 2023 + 2023BPix | 0.668524 +/- 0.015437 | 1.203479 +/- 0.049015 | 3.891691 +/- 0.154350 |
| 2024 | 1.115723 +/- 0.003833 | 0.420556 +/- 0.003879 | 0.605477 +/- 0.005224 |
| 2025 | 0.901812 +/- 0.003523 | 0.304427 +/- 0.003035 | 0.391088 +/- 0.003537 |

!!! warning "Weights at a boundary"
    Values printed as `0.000000` are positive values numerically compatible
    with zero (`2.3e-9` and `5.2e-18`) from a fit constrained to non-negative
    normalizations. Several values are also exactly or numerically very close
    to `0.9` or `1.0`. Such boundary values should not be interpreted using the
    symmetric Hessian error alone; the fit summary and validation plots should
    be checked.

## DY selected-jet multiplicity reweighting

### Method

- **Purpose:** correct the DY distribution of the number of selected jets.
- **Control region and categories:** `Z_sideband_ggF` and
  `Z_sideband_VBF` are treated independently.
- **Observable:** `N_SelectedJets`, with bins for 0 through 9 jets and an
  inclusive overflow bin for 10 or more jets.
- **Weight definition:** the correction is evaluated bin by bin as
  
  $$w(N_{\mathrm{jets}}) =
  \frac{N_{\mathrm{data}}-N_{\mathrm{non-DY}}}{N_{\mathrm{DY}}}.$$
- **Statistical error:** propagated from the data, non-DY and DY histogram bin
  errors. These errors are retained in the diagnostic ROOT histograms during
  derivation; the correctionlib JSON contains the nominal bin weights only.
- **Protection:** bins with insufficient DY yield fall back to unity, and the
  configured weight range is enforced. Values outside the tabulated jet range
  are clamped to the first or last bin.
- **Output inputs:** `isVBF` and `nSelectedJets`; an unknown category receives
  the default weight `1.0`.

## DY dilepton-pT reweighting

### Method

- **Purpose:** correct the shape of the dilepton transverse momentum,
  $p_{T}(\ell\ell)$ (`pt_mumu`).
- **Control region:** the Z sideband, split into `ggF_0J`, `ggF_1J`,
  `ggF_ge2J` and `VBF_ge2J` categories.
- **Raw ratio:** in every category, the starting points are
  $(N_{\mathrm{data}}-N_{\mathrm{non-DY}})/N_{\mathrm{DY}}$ with propagated
  histogram uncertainties.
- **Fit:** the ratio is fitted between 0 and 200 GeV with a constant plus two
  Gaussian terms and a falling-power term:

  $$f(x)=p_0+p_1e^{-\frac{1}{2}((x-p_2)/p_3)^2}
  +p_4e^{-\frac{1}{2}((x-p_5)/p_6)^2}
  +p_7\left(\frac{\max(x,p_8)}{p_8}\right)^{-p_9}.$$

- **Category behavior:** the fitted function is used for all three ggF jet
  bins and for the VBF category with at least two jets. VBF events with zero or
  one selected jet receive unity.
- **Uncertainty:** bin errors enter the fit and parameter errors are available
  in the derivation payload/ROOT output. The production correctionlib JSON
  stores the central fit parameters only; it does not expose an event-level
  up/down variation.
- **Output inputs:** `isVBF`, `N_selectedJets` and `ptll`; jet-count underflow
  and overflow are clamped and an unknown category receives `1.0`.

## Payload locations and application

The active files live under:

```text
reweights/dy_012j_reweight_Aug31/<payload-era>/dy_012j_reweight.json
reweights/dy_njets_reweight_Aug31/<payload-era>/dy_njets_reweight.json
reweights/dy_ptll_reweight_Aug31/<payload-era>/dy_ptll_reweight_smart.json
```

The era-specific `config/Run3_<era>/process_names.yaml` selects the appropriate
payload group. The selected-jet and dilepton-$p_T$ corrections are evaluated as
event weights during histogram production. The 0/1/2J correction acts on the
separately produced DY component templates.

