#!/bin/zsh
# Собирает мод «Честный пинг» без Gradle: игра 26.3 без запутывания имён, поэтому хватает javac
# из Java 25, которую Prism уже скачал, и библиотек игры из папки Prism. Готовый jar — в files/.
set -e
here=${0:A:h}
repo=${here:h:h}
prism="$HOME/Library/Application Support/PrismLauncher"
jdk="$prism/java/java-runtime-epsilon/bin"
version=$(sed -nE 's/.*"version": "([^"]+)".*/\1/p' $here/resources/fabric.mod.json)
out=$repo/files/chestnyi-ping-$version.jar

# ровно библиотеки 26.3 и Fabric из описаний Prism: в libraries лежат и другие версии игры,
# и javac взял бы первую попавшуюся
cp=$(python3 -I - "$prism" <<'EOF'
import json, sys
from pathlib import Path
P = Path(sys.argv[1])
jars = [P / "libraries/com/mojang/minecraft/26.3/minecraft-26.3-client.jar"]
for meta in ("net.minecraft/26.3.json", "net.fabricmc.fabric-loader/0.19.5.json"):
    for lib in json.loads((P / "meta" / meta).read_text()).get("libraries", []):
        g, a, v = lib["name"].split(":")[:3]
        jar = P / "libraries" / g.replace(".", "/") / a / v / f"{a}-{v}.jar"
        if jar.exists():
            jars.append(jar)
print(":".join(map(str, jars)))
EOF
)
rm -rf $here/build && mkdir -p $here/build/classes
"$jdk/javac" --release 25 -proc:none -encoding UTF-8 -cp "$cp" -d $here/build/classes $(find $here/src -name '*.java')
cp $here/resources/* $here/build/classes/
cp $repo/LICENSE $here/build/classes/LICENSE
rm -f $out
(cd $here/build/classes && "$jdk/jar" --create --file $out --date=2026-01-01T00:00:00Z .)
rm -rf $here/build
echo "собран: ${out#$repo/}"
