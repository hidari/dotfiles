;; extends

; 見出しマーカー (# ## ...) をレベルごとのキャプチャへ分ける。
; 既定クエリの @markup.heading.N は "# H1" の行全体 (改行まで) を覆っており、
; マーカー単独のキャプチャが無い。
; 拡張クエリのキャプチャは既定より後に評価されるため、範囲が重なったときに後勝ちする。
;
; キャプチャ名にレベルを含めるのが要点である。@markup.heading.N.marker は
; @ 名前空間の階層フォールバックで @markup.heading.N へ落ちるため、
; 色を一切定義しなくてもマーカーが見出しと同色になる。
; レベルを含まない @markup.heading.marker は @markup.heading (既定の Title) にしか落ちない。
;
; キャプチャ名がレベルごとに異なるため、交替リストにはまとめられない。
(atx_h1_marker) @markup.heading.1.marker
(atx_h2_marker) @markup.heading.2.marker
(atx_h3_marker) @markup.heading.3.marker
(atx_h4_marker) @markup.heading.4.marker
(atx_h5_marker) @markup.heading.5.marker
(atx_h6_marker) @markup.heading.6.marker
