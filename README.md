# Kirei TeX HTML Prototype

日本語数学教材向けの「1ファイル型インタラクティブ数学書」MVPです。
LaTeX風の `.ktex` 原稿から、ローカルで直接開ける単一HTMLを生成します。

## 使い方

```powershell
python src/build.py examples/sample.ktex dist/sample.html
```

生成後、`dist/sample.html` をブラウザで開きます。

このMVPではCSSとJavaScriptをHTMLへインライン展開します。数式表示にはMathJax CDNを使うため、初回表示時はインターネット接続が必要です。

## 対応している記法

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
\begin{kbox}[type=theorem,title=二階微分可能な関数の凸性判定]
本文
\end{kbox}
```

`type` は `theorem`、`note`、`example` などを想定しています。

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
\begin{kexercise}[title=演習: 混合項の強さを調べる,level=standard]
問題文
\end{kexercise}
```

演習問題用のボックスに変換されます。
`level` は `basic`、`standard`、`advanced` を想定しており、`kexercise-basic` のようなCSS classが付きます。

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

## サンプル題材

`examples/sample.ktex` は「二次形式とヘッセ行列」を題材にしています。

```tex
f(x,y)=x^2+y^2+3xy
```

のように、`x^2` と `y^2` の係数が正でも、混合項によって凸でなくなる例を扱っています。

## 現在の制限

- 完全なLaTeXパーサーではありません。
- 対応しているのは、自作マクロ `kfold`、`kgap`、`kbox`、`kadvanced`、`kproof`、`kexercise`、`khint`、`kanswer` と、簡単な見出しだけです。
- MathJax本体はHTMLへ同梱していません。
- 複雑なオプション構文や任意のLaTeX環境には未対応です。

## 今後の拡張方針

1. `.ktex` の構文エラー位置をわかりやすく表示する。
2. 目次、章番号、定理番号、参照 `\kref{...}` を追加する。
3. `\kgap` を脚注風・余白注風・ポップアップ風から選べるようにする。
4. MathJaxをローカル同梱できるビルドモードを追加する。
5. 教材向けに演習、解答、ヒント段階表示のマクロを追加する。
6. 最終的にLaTeXパッケージ化し、PDF向け出力とHTML向け出力を同じ原稿から分岐できるようにする。
