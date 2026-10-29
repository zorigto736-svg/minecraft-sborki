"""Собирает сборку для автообновления в Prism (формат packwiz) и архив для импорта в Prism.

Что получается в репозитории:
  <папка сборки>/pack.toml, index.toml, mods/*.pw.toml — список модов со ссылками на Modrinth
      и суммами; packwiz-installer при каждом запуске игры сверяется с ним и докачивает разницу;
  <папка сборки>/config/..., resourcepacks/... — файлы настроек из основы сборки;
  prism/<папка сборки>.zip — сборка для «Добавить сборку → Импорт → ссылка» в Prism.

Основа — модпак с Modrinth (.mrpack), поверх — свои моды (EXTRA_MODS) и свои файлы (EXTRA_FILES).
Чтобы добавить мод: дописать его адрес на Modrinth в EXTRA_MODS и запустить заново:
    python3 -I tools/build_pack.py <папка для скачанного>
"""
import hashlib
import io
import json
import shutil
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RAW = "https://raw.githubusercontent.com/zorigto736-svg/minecraft-sborki/main"
UA = {"User-Agent": "zorigto736-svg/minecraft-sborki"}
ALLOWED = {"cdn.modrinth.com"}

PACK = {
    "dir": "server-na-dvoih",
    "name": "Сервер на двоих — быстрая",
    "version": "1.1.0",
    "minecraft": "26.3",
    "lwjgl": "3.4.3",  # 26.3 просит 3.4.3; со старой 3.4.1 Sodium не запускает игру
    "base": "fabulously-optimized",  # модпак-основа на Modrinth
    "extra_mods": ["bobby"],
    # свои моды из этого репозитория (src-mods/…/build.sh кладёт jar в files/): качаются с GitHub
    "own_mods": ["files/chestnyi-ping-1.0.0.jar"],
    # свои файлы: путь в сборке → (откуда, preserve). preserve — только если файла ещё нет,
    # чтобы не затирать то, что игрок поменял сам (список серверов)
    "extra_files": {"servers.dat": ("files/servers.dat", True)},
    # настройки игры только для нового импорта: русский язык, размер интерфейса сам, окно
    "options": {"lang": "ru_ru", "guiScale": "0", "fullscreen": "false", "renderDistance": "12"},
}


def get(url):
    host = urllib.parse.urlparse(url).hostname
    assert host in ALLOWED | {"api.modrinth.com"}, f"чужой адрес: {url}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read()


def version_for(slug, mc):
    q = urllib.parse.urlencode({"game_versions": json.dumps([mc]), "loaders": '["fabric"]'})
    found = json.loads(get(f"https://api.modrinth.com/v2/project/{slug}/version?{q}"))
    assert found, f"{slug}: нет версии под {mc}"
    return found[0]


def toml_str(s):
    return json.dumps(s, ensure_ascii=False)


def mod_toml(name, filename, url, sha512, side):
    # cdn.modrinth.com/data/<проект>/versions/<версия>/<файл> — по ним packwiz умеет обновлять
    parts = urllib.parse.urlparse(url).path.split("/")
    lines = [f"name = {toml_str(name)}", f"filename = {toml_str(filename)}", f"side = {toml_str(side)}", "",
             "[download]", f"url = {toml_str(url)}", 'hash-format = "sha512"', f"hash = {toml_str(sha512)}"]
    if len(parts) > 4 and parts[1] == "data" and parts[3] == "versions":
        lines += ["", "[update]", "[update.modrinth]", f"mod-id = {toml_str(parts[2])}",
                  f"version = {toml_str(parts[4])}"]
    return "\n".join(lines) + "\n"


def side_of(env):
    env = env or {}
    if env.get("client") == "unsupported":
        return "server"
    if env.get("server") == "unsupported":
        return "client"
    return "both"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    cache = Path(sys.argv[1])
    cache.mkdir(parents=True, exist_ok=True)
    out = REPO / PACK["dir"]
    if out.exists():
        shutil.rmtree(out)
    out.mkdir()
    files = {}  # путь в сборке → (байты, metafile, preserve)

    base = version_for(PACK["base"], PACK["minecraft"])
    pf = next(f for f in base["files"] if f["filename"].endswith(".mrpack"))
    mrpack = cache / pf["filename"]
    if not mrpack.exists() or hashlib.sha512(mrpack.read_bytes()).hexdigest() != pf["hashes"]["sha512"]:
        data = get(pf["url"])
        assert hashlib.sha512(data).hexdigest() == pf["hashes"]["sha512"], "не сошлась сумма модпака"
        mrpack.write_bytes(data)
    with zipfile.ZipFile(mrpack) as z:
        index = json.loads(z.read("modrinth.index.json"))
        deps = index["dependencies"]
        assert deps["minecraft"] == PACK["minecraft"], deps
        for f in index["files"]:
            url = f["downloads"][0]
            assert urllib.parse.urlparse(url).hostname in ALLOWED, url
            folder, filename = f["path"].rsplit("/", 1)
            meta = f"{folder}/{Path(filename).stem.lower()}.pw.toml"
            files[meta] = (mod_toml(Path(filename).stem, filename, url, f["hashes"]["sha512"],
                                    side_of(f.get("env"))).encode(), True, False)
        default_options = b""
        for name in z.namelist():
            for prefix in ("overrides/", "client-overrides/"):
                if name.startswith(prefix) and not name.endswith("/"):
                    rel = name[len(prefix):]
                    assert ".." not in rel.split("/"), name
                    if rel == "config/modpack_defaults/options.txt":
                        default_options = z.read(name)
                    files[rel] = (z.read(name), False, False)
    print(f"основа: {base['name']} — модов {len(index['files'])}, файлов настроек {len(files) - len(index['files'])}")

    for slug in PACK["extra_mods"]:
        v = version_for(slug, PACK["minecraft"])
        f = next((x for x in v["files"] if x.get("primary")), v["files"][0])
        files[f"mods/{slug}.pw.toml"] = (mod_toml(slug, f["filename"], f["url"], f["hashes"]["sha512"],
                                                  "client").encode(), True, False)
        print(f"мод с Modrinth: {slug} {v['version_number']}")
    for src in PACK["own_mods"]:
        jar = REPO / src
        name = jar.stem.rsplit("-", 1)[0]
        files[f"mods/{name}.pw.toml"] = (mod_toml(name, jar.name, f"{RAW}/{src}",
                                                  hashlib.sha512(jar.read_bytes()).hexdigest(), "client").encode(),
                                         True, False)
        print(f"свой мод: {jar.name}")
    for rel, (src, preserve) in PACK["extra_files"].items():
        files[rel] = ((REPO / src).read_bytes(), False, preserve)

    entries = []
    for rel in sorted(files):
        data, metafile, preserve = files[rel]
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        e = [f"file = {toml_str(rel)}", f"hash = {toml_str(sha256(data))}"]
        if metafile:
            e.append("metafile = true")
        if preserve:
            e.append("preserve = true")
        entries.append("[[files]]\n" + "\n".join(e))
    index_toml = ('hash-format = "sha256"\n\n' + "\n\n".join(entries) + "\n").encode()
    (out / "index.toml").write_bytes(index_toml)
    (out / "pack.toml").write_text(
        f"name = {toml_str(PACK['name'])}\nauthor = \"ERAZAY\"\nversion = {toml_str(PACK['version'])}\n"
        'pack-format = "packwiz:1.1.0"\n\n[index]\nfile = "index.toml"\nhash-format = "sha256"\n'
        f"hash = {toml_str(sha256(index_toml))}\n\n[versions]\nfabric = {toml_str(deps['fabric-loader'])}\n"
        f"minecraft = {toml_str(PACK['minecraft'])}\n")
    print(f"сборка: {out.relative_to(REPO)} — файлов в списке {len(files)}")
    build_prism_zip(deps["fabric-loader"], default_options)


def build_prism_zip(loader, default_options):
    """Сборка для Prism: пустая игра нужной версии + установщик, который при запуске всё докачает."""
    pack_url = f"{RAW}/{PACK['dir']}/pack.toml"
    cfg = "\n".join([
        "[General]", "AutomaticJava=true", "ConfigVersion=1.3", "InstanceType=OneSix",
        "JoinServerOnLaunch=false", "ManagedPack=false", "OverrideCommands=true",
        # QSettings: значение в кавычках, кавычки внутри — через обратную косую
        'PreLaunchCommand="\\"$INST_JAVA\\" -jar packwiz-installer-bootstrap.jar --bootstrap-no-update '
        + pack_url + '"',
        "iconKey=default", f"name={PACK['name']} ({PACK['minecraft']})",
        "notes=Моды и настройки обновляются сами при каждом запуске: github.com/zorigto736-svg/minecraft-sborki",
    ]) + "\n"
    mmc = {"components": [
        {"dependencyOnly": True, "uid": "org.lwjgl3", "version": PACK["lwjgl"]},
        {"important": True, "uid": "net.minecraft", "version": PACK["minecraft"]},
        {"dependencyOnly": True, "uid": "net.fabricmc.intermediary", "version": PACK["minecraft"]},
        {"uid": "net.fabricmc.fabric-loader", "version": loader},
    ], "formatVersion": 1}
    opts, seen = [], set()
    for line in default_options.decode().splitlines():
        key = line.split(":", 1)[0]
        seen.add(key)
        opts.append(f"{key}:{PACK['options'][key]}" if key in PACK["options"] else line)
    opts += [f"{k}:{v}" for k, v in PACK["options"].items() if k not in seen]
    dst = REPO / "prism" / f"{PACK['dir']}.zip"
    dst.parent.mkdir(exist_ok=True)
    entries = {"instance.cfg": cfg.encode(), "mmc-pack.json": json.dumps(mmc, indent=4).encode(),
               "minecraft/options.txt": ("\n".join(opts) + "\n").encode()}
    for jar in ("packwiz-installer-bootstrap.jar", "packwiz-installer.jar"):
        entries[f"minecraft/{jar}"] = (REPO / "tools" / jar).read_bytes()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            # постоянная дата — архив меняется только когда меняется содержимое
            z.writestr(zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0)), data, zipfile.ZIP_DEFLATED)
    dst.write_bytes(buf.getvalue())
    print(f"для Prism: {dst.relative_to(REPO)} — {dst.stat().st_size / 1e6:.1f} МБ, ссылка {RAW}/prism/{dst.name}")


if __name__ == "__main__":
    main()
