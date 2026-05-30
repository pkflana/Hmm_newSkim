First, run voms-proxy-init --voms cms --valid 192:00, it will say "created proxy in some/location"
copy this file from where it is (typically the tmp folder) to somewhere permanent like afs.
Change proxy_location in skim_cfg.yaml to this location so you can export it. Then you run getfiles.py followed by 
condorsubmit.py, pretty much all options are controlled within skim_cfg.yaml
After jobs are done, run checkzombies.py to get a list of files that were successfully skimmed in completed_files.txt, which will then be skipped
on a subsequent running of condorsubmit.py