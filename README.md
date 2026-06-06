# Kirei TeX HTML Prototype

日本語数学教材向けの「1ファイル型インタラクティブ数学書」MVPです。
LaTeX風の `.ktex` 原稿から、ローカルで直接開ける単一HTMLを生成します。

## 使い方

```powershell
python src/build.py examples/sample.ktex dist/sample.html
```

生成後、`dist/sample.html` をブラウザで開きます。

このMVPではCSSとJavaScriptをHTMLへインライン展開します。数式表示にはMathJax CDNを使うため、初回表示時はインターネット接続が必要です。

### 構文チェック

HTMLを出力せず、原稿の構文だけを確認できます。

```powershell
python src/build.py examples/sample.ktex dist/sample.html --check
```

warning も error として扱いたい場合は `--strict` を付けます。

```powershell
python src/build.py examples/sample.ktex dist/sample.html --strict
```

warning の詳細表示を抑えたい場合は `--quiet` を付けます。

```powershell
python src/build.py examples/sample.ktex dist/sample.html --quiet
```

通常は error があるとHTMLを出力しません。
壊れている箇所を画面上で確認したい場合だけ、`--allow-output-on-error` を使うと可能な範囲でHTMLを出力します。

```powershell
python src/build.py examples/broken.ktex dist/broken.html --allow-output-on-error
```

### warning と error

`warning` はHTML出力を継続できる問題です。
たとえば未解決の `\kref{...}` や、不正な `kexercise` の `level` が該当します。

`error` はデフォルトではHTML出力を止める問題です。
たとえば環境の閉じ忘れや、`label` の重複が該当します。

よくある例:

- `\end` の閉じ忘れ: `\begin{kbox}` に対応する `\end{kbox}` がない。
- `label` 重複: 同じ `label=thm:hessian` を複数の `kbox` / `kexercise` で使っている。
- 未解決 `\kref`: `\kref{thm:missing}` の参照先ラベルが存在しない。
- 不正な `level`: `kexercise` の `level` は `basic`、`standard`、`advanced` のみ正式対応。

エラー確認用のサンプルとして `examples/broken.ktex` があります。

```powershell
python src/build.py examples/broken.ktex dist/broken.html --check
```

## 対応している記法

### 見出し番号と目次

```tex
\section{二次形式を眺める}
\subsection{二階微分による凸性判定}
\subsubsection{方向微分で見る}
```

見出しは自動で `1. タイトル`、`1.1 タイトル`、`1.1.1 タイトル` のように番号付きで出力されます。
各見出しには `section-1`、`section-1-1`、`section-1-1-1` のようなHTML `id` が付きます。

HTML冒頭には `class="ktoc"` の自動目次が生成されます。
目次は `details` / `summary` で表示され、デフォルトでは開いた状態です。

### 折りたたみ

```tex
\begin{kfold}[title=固有値で見る]
本文
\end{kfold}
```

HTMLの `<details>` / `<summary>` に変換されます。

### 注釈

```tex
本文中に \kgap{補足説明} を置けます。
```

本文中の小さな `?` ボタンになり、クリックまたはタップで注釈を表示します。

### ボックス

```tex
\begin{kbox}[type=theorem,title=ヘッセ行列による凸性判定,label=thm:hessian]
本文
\end{kbox}
```

`label` を付けると、そのボックスに安全なHTML `id` が付き、`\kref{...}` で参照できます。

番号付きで扱う `type` は次の通りです。

- `theorem`: 定理
- `definition`: 定義
- `proposition`: 命題
- `lemma`: 補題
- `corollary`: 系
- `example`: 例
- `exercise`: 演習

`note` は番号なしの注意ボックスとして扱います。
番号は章ごとにリセットされ、表示は `定理 1.1（ヘッセ行列による凸性判定）` のようになります。

### 発展トグル

```tex
\begin{kadvanced}
発展的な本文
\end{kadvanced}
```

画面上部の「発展を表示」トグルで表示・非表示を切り替えます。

### 証明

```tex
\begin{kproof}
証明本文
\end{kproof}
```

「証明」というラベル付きの折りたたみボックスに変換されます。
デフォルトでは閉じており、末尾にQED記号 `□` を表示します。

### 演習

```tex
\begin{kexercise}[title=混合項の強さ,label=ex:mixed-term,level=standard]
問題文
\end{kexercise}
```

演習問題用のボックスに変換されます。
`level` は `basic`、`standard`、`advanced` を想定しており、`kexercise-basic` のようなCSS classが付きます。
`label` を付けるとHTML `id` が付き、`\kref{...}` で参照できます。
表示は `演習 1.2（混合項の強さ）` のようになります。

### ヒント

```tex
\begin{khint}[title=考え方]
ヒント本文
\end{khint}
```

ヒント用の折りたたみに変換されます。
`title` を省略した場合のデフォルトタイトルは「ヒント」です。

### 解答

```tex
\begin{kanswer}[title=解答例]
解答本文
\end{kanswer}
```

解答用の折りたたみに変換されます。
`title` を省略した場合のデフォルトタイトルは「解答」です。

### ラベル参照

```tex
\kref{thm:hessian} より、ヘッセ行列を調べればよい。
```

`\kref{...}` は、対応する `label` を持つ `kbox` または `kexercise` へのリンクに変換されます。
表示文字列は `定理 1.1`、`例 1.2`、`演習 1.3` のようになります。
存在しないラベルを参照した場合は、赤字の `??` として表示されます。

## サンプル題材

`examples/sample.ktex` は「二次形式とヘッセ行列」を題材にしています。

```tex
f(x,y)=x^2+y^2+3xy
```

のように、`x^2` と `y^2` の係数が正でも、混合項によって凸でなくなる例を扱っています。

## 現在の制限

- 完全なLaTeXパーサーではありません。
- 対応しているのは、自作マクロ `kfold`、`kgap`、`kbox`、`kadvanced`、`kproof`、`kexercise`、`khint`、`kanswer`、`\kref` と、簡単な見出しだけです。
- `label` 参照に対応しているのは、現在 `kbox` と `kexercise` です。
- 番号付きボックスと演習は、章ごとの共有カウンタで番号付けされます。
- 診断は簡易的な構文走査に基づくため、完全なLaTeX文法チェックではありません。
- MathJax本体はHTMLへ同梱していません。
- 複雑なオプション構文や任意のLaTeX環境には未対応です。

## テスト

Python標準ライブラリの `unittest` で簡易テストを実行できます。

```powershell
python -m unittest discover tests
```

## 今後の拡張方針

1. `.ktex` の構文エラー位置をわかりやすく表示する。
2. `\kgap` を脚注風・余白注風・ポップアップ風から選べるようにする。
3. MathJaxをローカル同梱できるビルドモードを追加する。
4. 段階ヒント機能を強化し、複数ヒントや表示順制御を扱えるようにする。
5. 最終的にLaTeXパッケージ化し、PDF向け出力とHTML向け出力を同じ原稿から分岐できるようにする。
