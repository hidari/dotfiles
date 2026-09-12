##################################
# .zshenv — 全ての zsh 起動が読む設定

# ここへ置いてよいのは、非対話シェル (zsh -c) にも届く必要がある環境変数だけ。
# 対話シェル向けの設定と PATH は .zshrc が持つ。PATH をここへ移しても Claude Code の
# シェルスナップショットが最終行で起動元シェルの値へ上書きするため効かない。
#
# 出力を一切行わないこと。.zshenv は scp / sftp / rsync over ssh の非対話セッションでも
# 読まれるため、1 バイトでも印字するとプロトコルが壊れる。

# 禁止語ガードが読むリストの在り処。検査本体は agentic-coding-tools が持つ。
#
# 指すのは中立な固定パスで、そこを追跡外のリスト実体への symlink として人が手で張る。
# 実体のパスをこの PUBLIC リポジトリへ書かないための間接参照であり、張り先は各マシンが
# 決める。bootstrap はこの symlink を作らない。作ると下のガードが全マシンで真になり、
# リストを持たないマシンで検査が毎回 rc=2 になる。
#
# 判定に -L を使うのは、壊れた symlink を「不在」ではなく「張ってある」側へ入れるため。
# -r や -e だと実体を引けない状態が未設定と同じ扱いになり、検査不能で止まるべき場面が
# 静かな skip に化ける。
if [ -L "$HOME/.config/leak-guard/denylist.gitignore" ]; then
  export LEAK_GUARD_DENYLIST="$HOME/.config/leak-guard/denylist.gitignore"
fi
