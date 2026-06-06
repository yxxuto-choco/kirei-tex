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

## サンプル題材

`examples/sample.ktex` は「二次形式とヘッセ行列」を題材にしています。

```tex
f(x,y)=x^2+y^2+3xy
```

のように、`x^2` と `y^2` の係数が正でも、混合項によって凸でなくなる例を扱っています。

## 現在の制限

- 完全なLaTeXパーサーではありません。
- 対応しているのは、自作マクロ `kfold`、`kgap`、`kbox`、`kadvanced` と、簡単な見出しだけです。
- MathJax本体はHTMLへ同梱していません。
- 複雑なオプション構文や任意のLaTeX環境には未対応です。

## 今後の拡張方針

1. `.ktex` の構文エラー位置をわかりやすく表示する。
2. 目次、章番号、定理番号、参照 `\kref{...}` を追加する。
3. `\kgap` を脚注風・余白注風・ポップアップ風から選べるようにする。
4. MathJaxをローカル同梱できるビルドモードを追加する。
5. 教材向けに演習、解答、ヒント段階表示のマクロを追加する。
6. 最終的にLaTeXパッケージ化し、PDF向け出力とHTML向け出力を同じ原稿から分岐できるようにする。
