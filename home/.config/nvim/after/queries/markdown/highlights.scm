;; extends

; 見出しマーカー (# ## ...) を見出し本体と別グループへ分け、色を分けられるようにする。
; 既定クエリの @markup.heading.N は "# H1" の行全体を覆っており、マーカー単独のキャプチャが無い。
; 拡張クエリのキャプチャは既定より後に評価されるため、範囲が重なったときに後勝ちする。
[
  (atx_h1_marker)
  (atx_h2_marker)
  (atx_h3_marker)
  (atx_h4_marker)
  (atx_h5_marker)
  (atx_h6_marker)
] @markup.heading.marker
