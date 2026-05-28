import tarfile

tar_name = "framework.tar.gz"

with tarfile.open(tar_name, "w:gz") as tar:
    tar.add("analysis")
    tar.add("config")
    tar.add("corrections")
    tar.add("skimProduction")
    tar.add("env.sh")

print(f"[INFO] created {tar_name}")