---
paths: ["**/*.tsx", "**/*.jsx", "**/*.html", "**/*.css"]
---

# [MUST] 見た目ではなく意味で組み、色だけに情報を載せない

- 適切なセマンティックHTML要素を使用する（nav, main, article, footer など）
- Web開発では modern-web-guidance plugin を活用し常に最新で安全なWeb実装を行うこと
- a11yを重視しフォーカス可能な要素にはキーボード操作を確保する
- i18n対応する場合は aria-label や aria-describedby などのARIA属性も対応する
- デザインでは色だけに依存しない情報伝達を行う
- レスポンシブ画像で CLS 予約用の `width`/`height` 属性と CSS の `aspect-ratio` を併用するときは、CSS に必ず `height: auto`（縦基準なら `width: auto`）を入れる（理由: `width` と `height` の両方が確定すると CSS の `aspect-ratio` は無視され、`height` 属性の値で画像が縦伸び・クロップする。`height: auto` で属性値による固定を外し `aspect-ratio` に高さを算出させる）
