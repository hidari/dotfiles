;; extends

; 見出しマーカー (# ## ...) をレベルごとのキャプチャへ分ける。
; 既定クエリの @markup.heading.N は "# H1" の行全体 (改行まで) を覆っており、
; マーカー単独のキャプチャが無い。
; 拡張クエリのキャプチャは既定より後に評価されるため、範囲が重なったときに後勝ちする。
;
; キャプチャ名にレベルを含めるのが要点である。色は config/markdown.lua が
; @markup.heading.N.marker.markdown へ明示的に与え、見出しと同色にする。
; 見出しを @markup.heading.N.markdown へスコープしたため素の @markup.heading.N は無く、
; @ 名前空間の階層フォールバック (右から削る) では見出し色を継承できないので明示定義する。
; レベルを含まない @markup.heading.marker では見出しごとに色を分けられない。
;
; キャプチャ名がレベルごとに異なるため、交替リストにはまとめられない。
(atx_h1_marker) @markup.heading.1.marker
(atx_h2_marker) @markup.heading.2.marker
(atx_h3_marker) @markup.heading.3.marker
(atx_h4_marker) @markup.heading.4.marker
(atx_h5_marker) @markup.heading.5.marker
(atx_h6_marker) @markup.heading.6.marker
