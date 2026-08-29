# EviLife Android

原生 Kotlin + Jetpack Compose 客户端，与网页和 iOS 共用 EviLife FastAPI 后端及数据库。界面采用与 iOS 端一致的浅色、青绿色、底部标签栏布局。

## 功能

- 注册、Cookie 会话登录、启动时恢复会话和退出登录
- 生活版/专业版循证问答（`/api/v1/orchestrate`），支持图片、PDF、TXT、CSV 附件；回答和模式保存到账号历史
- 最近对话列表、打开历史对话和删除对话（与网页版共用）
- 今日记录摘要和进食间隔计时（与网页版共用）
- 健康档案：读取/新增饮水、步数、睡眠、体重、腰围、静息心率、心情和备注，并调用服务端健康档案分析
- 体检报告上传和服务端摘要（PDF、TXT、CSV、JPG、PNG、WebP）
- Android Health Connect 授权，读取最近 30 天步数、睡眠、静息心率和体重，按天聚合并幂等上传
- 网页二维码扫码配对（`/api/v1/device-pairing/claim`）
- 设置页修改服务器地址

Android 不直接连接数据库；Android 和网页版都通过同一个 FastAPI 后端访问
`backend/.data/runtime.sqlite3`，因此账号、对话、进食计时和健康观察记录可以互通。

## 构建

需要 Android Studio Ladybug 或更新版本、JDK 17、Android SDK 35。打开此目录后执行：

```powershell
./gradlew.bat assembleDebug
```

工程已包含 Gradle Wrapper；首次构建会按 `gradle/wrapper/gradle-wrapper.properties` 使用 Gradle 8.9。

APK 输出：`app/build/outputs/apk/debug/app-debug.apk`。

USB 联调时，在电脑上启动后端 `127.0.0.1:8000`，执行：

```powershell
adb reverse tcp:8010 tcp:8000
```

应用默认访问 `http://127.0.0.1:8010`。也可以让手机与后端处于同一 Wi-Fi，在设置页填写电脑局域网地址，例如
`http://192.168.1.20:8000`。网页打开 `/pairing-qr.html` 生成二维码，Android 健康页点击扫码绑定；随后授权 Health Connect 并同步。生产环境请使用 HTTPS，并关闭明文流量。
