# OpenDisplay 軽量版 / Lightweight

[OpenDisplay](https://github.com/peetzweg/opendisplay) v1.30.1を基に、変化していないカーソル画像のTIFF変換を省く修正を加えた実験用フォークです。元の開発者による公式配布ではありません。ソース、ビルド手順、実機比較データを公開しています。

**[アプリをダウンロード（実験版）](https://github.com/Akira-Motoyoshi/opendisplay-lightweight/releases/tag/lightweight-v1.30.1-1)**

配布アプリは **Intel（x86_64）、macOS 14以降向け**です。アドホック署名で、Appleの公証は受けていません。Apple Siliconのネイティブビルドや他の機種での動作は検証していません。既存のiPad受信アプリを使用します。

## 実機比較

MacBook Air（Intel、8 GB、macOS 15.8.1）とiPadをUSBで接続し、H.264・1640×2360・同じアニメーション・カーソル静止の条件で比較しました。順序は軽量版→通常版→通常版→軽量版、各20秒の準備後に60秒計測、各版2回です。

| 指標 | 通常版 1.30.1 | 軽量版 | 差 |
| --- | ---: | ---: | ---: |
| アプリCPU（1論理CPU＝100%） | 64.25% | 54.59% | 約15.0%減 |
| メモリ実使用量（footprint） | 33.52 MiB | 34.90 MiB | 1.38 MiB増 |
| 転送fps | 23.09 | 25.18 | 約9.1%増 |
| Mac全体CPU（全CPU合計＝100%） | 82.36% | 84.88% | 2.51ポイント増 |

この条件ではアプリCPUの低下とfpsの増加を観測しました。**メモリ削減とMac全体のCPU負荷低減は確認していません。** 他のアプリの負荷やスワップは変動しています。通常版は公式バイナリ、軽量版はローカル開発ビルドで、コンパイラ・ビルド条件の違いも含みます。パッチ単独の因果効果、統計的有意性、長時間利用、電力削減を示す結果ではありません。

- [計測条件・各試行・数値データ](results/2026-11-04-usb-baab/README.md)
- [修正内容とビルド手順](LIGHTWEIGHT.md)
- [元のOpenDisplay README](UPSTREAM_README.md)

## 利用方法

1. ReleaseのZIPを展開し、`OpenDisplay Dev.app`を任意のアプリ保存場所にコピーします。既存の通常版とは別のアプリとして扱ってください。
2. 開く際にmacOSの警告が出る場合は、配布元とチェックサムを確認し、OSの案内に従ってください。
3. 初回使用時に「画面収録」の許可が必要です。タッチ操作には「アクセシビリティ」の許可も必要です。
4. 同じiPadへの接続には通常版と軽量版のどちらか一方を使います。通常版へ戻すときは、軽量版を終了して通常版を開きます。

開発版の自動アップデート確認は無効です。バンドルIDは`com.peetzweg.opensidecar.mac.debug`です。許可後の再ビルド・再署名で権限の再設定が必要になることがあります。

## ソースからの確認

```sh
git clone --branch lightweight https://github.com/Akira-Motoyoshi/opendisplay-lightweight.git
cd opendisplay-lightweight
zsh local-tools/check-cursor-fingerprint.sh
python3 local-tools/analyze-published-results.py
```

カーソル判定の単体チェック14項目が通過しています。同じ画像500回の単体測定は旧処理989.955 ms、新処理31.907 msでした。これは判定処理だけの測定で、アプリ全体の速度比ではありません。

実験で使ったIntel版は、Command Line Tools（Swift 6.1.2、Swift 5モード）で次の補助手順によりビルドしました。`/Applications/OpenDisplay.app` 1.30.1と、その中のSparkle 2.10.1が必要です。スクリプトは既存の正式版を書き換えません。通常のXcodeビルドについては[元の手順](UPSTREAM_README.md)と`project.yml`を参照してください。

```sh
python3 local-tools/build-dev-with-clt.py
./run.sh
```

`local-tools/compare-apps.py`は再計測用です。実行すると通常版と開発版を切り替えます。テスト用ディスプレイIDは環境に合わせた変更が必要です。事前に[計測手順](results/2026-11-04-usb-baab/README.md)を確認してください。結果の再集計だけなら`analyze-published-results.py`を使用します。

## 出典とライセンス

基準はOpenDisplay v1.30.1、コミット`c7c645d9fa46a9ced3b875c6a1e4e474f6a716cc`です。カーソル修正は`4e376c04f5fee832453d2e6473b87a2b05cb1fe0`、実験用コードは`af5666d1818c3699049107fc6c97896151088d40`にあります。このフォークは上流のソースと履歴、著作権表示を保持します。

OpenDisplayのソース・修正は[GPL-3.0](LICENSE)です。配布アプリに含まれるSparkle 2.10.1と関連コードのライセンスは[こちら](licenses/Sparkle-2.10.1-LICENSE.txt)を参照してください。[第三者コンポーネントの出典](THIRD_PARTY_NOTICES.md)も掲載しています。
