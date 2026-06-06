# Kirei TeX HTML Prototype

日本語数学教材向けの `.ktex` から、ローカルで読めるHTMLを生成するプロトタイプです。LaTeX風の原稿に、折りたたみ、注釈、定理ボックス、演習、参照、目次を加えて、数学ノートとして読める形に変換します。

## 使い方

単一ファイルをビルドする場合:

```powershell
python src/build.py examples/sample.ktex dist/sample.html
```

複数章の book manifest をビルドする場合:

```powershell
python src/build.py --book examples/book.kirei.yml dist/book.html
```

生成されたHTMLはブラウザで直接開けます。Webサーバーは不要です。

## Book Mode

`--book` を付けると、入力ファイルを `.kirei.yml` manifest として読みます。

```yaml
title: Kirei TeX 数学ノート
subtitle: 折りたたみと注釈で読む日本語数学教材
chapters:
  - path: chapters/01-quadratic-hessian.ktex
    title: 二次形式とヘッセ行列
  - path: chapters/02-eigen-svd-information.ktex
    title: 固有値分解・特異値分解と情報量（自由度）
```

`chapters[].path` は manifest ファイルからの相対パスとして解決されます。外部YAMLライブラリは使わず、`title`、`subtitle`、`chapters`、各章の `path` / `title` だけを読む簡易パーサーです。

`examples/book.kirei.yml` には、次の2章を収録しています。

- 第1章: 二次形式とヘッセ行列
- 第2章: 固有値分解・特異値分解と情報量（自由度）

第2章は第1章の補論ではなく、線形代数・次元圧縮・情報量を扱う独立した別話題の章です。

## 番号体系

単一ファイル mode では、従来通り `\section` を基準に番号が付きます。

book mode では chapter を基準に番号が付きます。

- chapter: `chapter-1`, `chapter-2`
- section: `1.1`, `1.2`, `2.1`
- subsection: `1.1.1`, `2.1.1`
- theorem / definition / proposition / lemma / corollary / example / exercise: `定理 1.1`, `例 1.1`, `演習 2.1`

book mode の label と `\kref{...}` は章をまたいで参照できます。同じ label が別章に重複している場合は error になります。

## 対応記法

### 見出し

```tex
\section{タイトル}
\subsection{タイトル}
\subsubsection{タイトル}
```

見出しには自動番号とHTML `id` が付き、本文冒頭に `class="ktoc"` の自動目次が生成されます。book mode では目次に chapter も表示されます。

### 折りたたみ

```tex
\begin{kfold}[title=固有値で見る]
本文
\end{kfold}
```

### 注釈

```tex
本文中に \kgap{短い補足説明} を置けます。
```

小さな `?` ボタンとして表示され、クリックまたはタップで注釈が開きます。

### ボックス

```tex
\begin{kbox}[type=theorem,title=ヘッセ行列による凸性判定,label=thm:hessian]
本文
\end{kbox}
```

対応している `type`:

- `theorem`: 定理
- `definition`: 定義
- `proposition`: 命題
- `lemma`: 補題
- `corollary`: 系
- `example`: 例
- `note`: 注意（番号なし）

`label` を付けるとHTML `id` が付き、`\kref{...}` で参照できます。

### 証明

```tex
\begin{kproof}
証明本文
\end{kproof}
```

「証明」という折りたたみとして表示され、末尾に QED 記号が付きます。デフォルトでは閉じています。

### 演習・ヒント・解答

```tex
\begin{kexercise}[title=混合項の強さ,label=ex:mixed-term,level=standard]
問題文

\begin{khint}
ヒント本文
\end{khint}

\begin{kanswer}
解答本文
\end{kanswer}
\end{kexercise}
```

`level` は `basic`、`standard`、`advanced` に対応しています。不明な値は warning になり、表示上は `standard` として扱われます。

### 発展

```tex
\begin{kadvanced}
発展的な本文
\end{kadvanced}
```

画面上部のトグルで表示/非表示を切り替えます。非表示時も「発展内容があります」という案内カードを残します。

### 参照

```tex
第1章の \kref{thm:hessian} を使う。
```

存在する label はリンクに変換されます。存在しない label はHTML上では `??` と表示され、CLIでは warning になります。`--strict` では error になります。

## MathJax

デフォルトは CDN mode です。

```powershell
python src/build.py examples/sample.ktex dist/sample.html --mathjax cdn
```

ローカルの MathJax を使う場合:

```powershell
python src/build.py examples/sample.ktex dist/sample-local.html --mathjax local
```

デフォルトでは次の配置を参照します。

```text
vendor/
  mathjax/
    tex-svg.js
```

別の場所に置く場合は `--mathjax-path` を使います。

```powershell
python src/build.py examples/sample.ktex dist/sample-local.html --mathjax local --mathjax-path vendor/mathjax/tex-svg.js
```

MathJaxを読み込まない場合:

```powershell
python src/build.py examples/sample.ktex dist/sample-none.html --mathjax none
```

`none` では `$x^2$` のようなTeXソースは変換されません。数式なし文書、または既に数式変換済みのHTML向けです。

## Assets

CSS/JS はデフォルトでHTMLにインライン展開されます。

```powershell
python src/build.py examples/sample.ktex dist/sample.html --assets inline
```

外部ファイルとして出力する場合:

```powershell
python src/build.py examples/sample.ktex dist/sample-external.html --assets external
```

この場合、`dist/assets/kirei.css` と `dist/assets/kirei.js` がコピーされ、HTMLから相対パスで読み込まれます。

## Offline

ネット接続なしで読む構成に近づける場合は `--offline` を使います。

```powershell
python src/build.py examples/sample.ktex dist/sample-offline.html --offline
python src/build.py --book examples/book.kirei.yml dist/book-offline.html --offline
```

`--offline` は次と同じ扱いです。

```text
--mathjax local --assets inline
```

注意: 現時点ではMathJax本体をHTMLへ完全インライン埋め込みしていません。完全オフラインで数式を表示するには、`vendor/mathjax/tex-svg.js` を事前に配置してください。

## 構文チェックと診断

HTMLを出力せずにチェックする場合:

```powershell
python src/build.py examples/sample.ktex dist/sample.html --check
python src/build.py --book examples/book.kirei.yml dist/book.html --check
```

warning も error として扱う場合:

```powershell
python src/build.py examples/sample.ktex dist/sample.html --strict
```

warning の詳細表示を抑える場合:

```powershell
python src/build.py examples/sample.ktex dist/sample.html --quiet
```

error があっても可能な範囲でHTMLを出したい場合:

```powershell
python src/build.py examples/broken.ktex dist/broken.html --allow-output-on-error
```

warning はHTML出力を続けられる問題、error はデフォルトではHTML出力を止める問題です。

よくある診断:

- `\end` の閉じ忘れ
- 未対応の `\begin{...}`
- `label` の重複
- 未解決の `\kref{...}`
- 不正な `kexercise` の `level`
- 不正な book manifest

壊れたサンプルは `examples/broken.ktex` です。

```powershell
python src/build.py examples/broken.ktex dist/broken.html --check
```

## テスト

Python標準ライブラリの `unittest` で実行できます。

```powershell
python -m unittest discover tests
```

## 現在の制限

- 完全なLaTeXパーサーではありません。
- 対応しているのは、Kirei TeX 独自マクロと簡易的な見出しです。
- `label` 参照に対応しているのは、現在 `kbox` と `kexercise` です。
- manifest パーサーは簡易YAML風で、複雑なYAML構文には対応していません。
- MathJax本体は `vendor/mathjax/tex-svg.js` として配置できますが、HTMLへの完全インライン埋め込みは未対応です。

## 今後の拡張方針

1. より高度な構文診断・修復提案を追加する。
2. `\kgap` を脚注風・傍注風・ポップアップ風から選べるようにする。
3. MathJax本体の取得・配置を支援するセットアップコマンドを追加する。
4. 段階ヒント機能を強化し、複数ヒントや表示順制御を扱えるようにする。
5. 最終的にLaTeXパッケージ化し、PDF向け出力とHTML向け出力を同じ原稿から切り替えられるようにする。
