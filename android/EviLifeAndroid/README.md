# EviLife Android

原生 Kotlin + Jetpack Compose 客户端，与网页和 iOS 共用 EviLife FastAPI 后端及数据库。界面采用与 iOS 端一致的浅色、青绿色、底部标签栏布局。

## 功能

- Cookie 会话登录
- 循证问答（`/api/v1/orchestrate`）
- 网页二维码扫码配对（`/api/v1/device-pairing/claim`）
- Android Health Connect 授权，读取最近 30 天步数和体重并幂等上传
- 设置页修改局域网服务器地址

## 构建

需要 Android Studio Ladybug 或更新版本、JDK 17、Android SDK 35。打开此目录后执行：

```powershell
./gradlew.bat assembleDebug
```

APK 输出：`app/build/outputs/apk/debug/app-debug.apk`。

真机测试时让手机与后端处于同一 Wi-Fi，在设置页填写例如 `http://192.168.1.20:8000`。网页打开 `/pairing-qr.html` 生成二维码，Android 健康页点击扫码绑定；随后授权 Health Connect 并同步。生产环境请使用 HTTPS，并关闭明文流量。
