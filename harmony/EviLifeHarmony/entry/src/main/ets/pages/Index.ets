import { common } from '@kit.AbilityKit';
import { BusinessError } from '@kit.BasicServicesKit';
import { ApiClient } from '../common/ApiClient';
import { LocalStore } from '../common/LocalStore';
import { PairingParser, PairingPayload } from '../common/PairingParser';
import { ScanService } from '../common/ScanService';
import { HealthObservation, HealthSyncService, SyncReport } from '../common/HealthSyncService';

const BG_COLOR: string = '#F2F2F7';
const CARD_COLOR: string = '#FFFFFF';
const TEXT_COLOR: string = '#1C1C1E';
const SUBTEXT_COLOR: string = '#8E8E93';
const BRAND_COLOR: string = '#0F766E';
const BRAND_SOFT_COLOR: string = '#E6F4F1';
const BORDER_COLOR: string = '#E5E5EA';
const DANGER_COLOR: string = '#FF3B30';

@Entry
@Component
struct Index {
  @State tab: number = 0;
  @State email: string = '';
  @State password: string = '';
  @State question: string = '';
  @State server: string = 'http://172.20.10.10:8010';
  @State logged: boolean = false;
  @State status: string = '';
  @State answer: string = '';
  @State pairingCode: string = '';
  @State syncStatus: string = '';
  @State busy: boolean = false;

  aboutToAppear(): void {
    this.restore();
  }

  async restore(): Promise<void> {
    const context = getContext(this) as common.UIAbilityContext;
    await LocalStore.shared().init(context);
    const savedServer = await LocalStore.shared().getString('server', '');
    if (savedServer.length > 0) {
      this.server = savedServer;
    }
    ApiClient.shared().setServer(this.server);
    const savedEmail = await LocalStore.shared().getString('email', '');
    if (savedEmail.length > 0) {
      this.email = savedEmail;
    }
  }

  async saveServer(): Promise<void> {
    ApiClient.shared().setServer(this.server);
    await LocalStore.shared().putString('server', ApiClient.shared().server);
    this.status = '服务器地址已保存';
  }

  async login(): Promise<void> {
    if (this.email.length === 0 || this.password.length === 0) {
      this.status = '请输入邮箱和密码';
      return;
    }
    this.busy = true;
    this.status = '正在登录…';
    try {
      const body: Record<string, Object> = { 'email': this.email, 'password': this.password };
      await ApiClient.shared().postJson('/api/v1/auth/login', body);
      this.logged = true;
      this.status = '登录成功';
      await LocalStore.shared().putString('email', this.email);
    } catch (err) {
      this.status = ApiClient.errorMessage(err as Error);
    } finally {
      this.busy = false;
    }
  }

  async register(): Promise<void> {
    if (this.email.length === 0 || this.password.length === 0) {
      this.status = '请输入邮箱和密码';
      return;
    }
    this.busy = true;
    this.status = '正在注册…';
    try {
      const body: Record<string, Object> = { 'email': this.email, 'password': this.password };
      await ApiClient.shared().postJson('/api/v1/auth/register', body);
      this.logged = true;
      this.status = '注册成功，已登录';
      await LocalStore.shared().putString('email', this.email);
    } catch (err) {
      this.status = ApiClient.errorMessage(err as Error);
    } finally {
      this.busy = false;
    }
  }

  async logout(): Promise<void> {
    try {
      await ApiClient.shared().postJson('/api/v1/auth/logout', {});
    } catch (err) {
      // 忽略登出接口异常，直接清除本地登录态
    }
    this.logged = false;
    this.password = '';
    this.answer = '';
    this.status = '已退出登录';
    await LocalStore.shared().remove('email');
  }

  async ask(): Promise<void> {
    const text = this.question.trim();
    if (text.length === 0) {
      return;
    }
    this.busy = true;
    this.status = '正在分析…';
    this.answer = '';
    try {
      const sessionId = Date.now().toString();
      const encoded = 'session_id=' + encodeURIComponent(sessionId) + '&mode=auto&text=' + encodeURIComponent(text);
      const raw = await ApiClient.shared().postForm('/api/v1/orchestrate', encoded);
      this.answer = this.extractAnswer(raw);
      this.status = this.gateStatus(raw);
    } catch (err) {
      this.status = ApiClient.errorMessage(err as Error);
    } finally {
      this.busy = false;
    }
  }

  private gateStatus(raw: Record<string, Object>): string {
    const gate = raw['gate_status'];
    if (gate === 'refused') {
      return '已按安全边界拒绝该问题';
    }
    if (gate === 'degraded') {
      return '证据不完整，回答仅供参考';
    }
    return '回答已生成';
  }

  private extractAnswer(raw: Record<string, Object>): string {
    const parts: string[] = [];
    const plan = raw['module_plan'];
    if (plan instanceof Array) {
      for (let i = 0; i < plan.length; i++) {
        const item = plan[i] as Record<string, Object>;
        const props = item['props'];
        if (props instanceof Object && !(props instanceof Array)) {
          const propsRecord = props as Record<string, Object>;
          const textKeys: string[] = [
            'answer',
            'conclusion',
            'explanation',
            'general_advice',
            'verdict_detail',
            'one_sentence_summary'
          ];
          for (let k = 0; k < textKeys.length; k++) {
            const value = propsRecord[textKeys[k]];
            if (typeof value === 'string' && value.length > 0) {
              parts.push(value);
            }
          }
          const keyPointsValue = propsRecord['key_points'];
          if (keyPointsValue instanceof Array) {
            const keyPoints = keyPointsValue as Array<Object>;
            for (let j = 0; j < keyPoints.length; j++) {
              const point = keyPoints[j];
              if (typeof point === 'string' && point.length > 0) {
                parts.push('• ' + point);
              }
            }
          }
        }
      }
    }
    if (parts.length === 0) {
      return '暂无文字回答，该问题可能由专业模块处理，请在网页端查看完整结果。';
    }
    let result = '';
    for (let i = 0; i < parts.length; i++) {
      if (i > 0) {
        result += '\n\n';
      }
      result += parts[i];
    }
    return result;
  }

  async scanToBind(): Promise<void> {
    this.busy = true;
    this.status = '正在打开扫码…';
    try {
      const context = getContext(this) as common.UIAbilityContext;
      const result = await ScanService.scan(context);
      const payload = PairingParser.parse(result.originalValue);
      if (payload === null) {
        this.status = '未识别到有效的 EviLife 配对内容';
        return;
      }
      if (payload.code.length > 0) {
        this.status = '正在绑定账号…';
        const email = await HealthSyncService.claimDevicePairing(payload.code);
        this.logged = true;
        this.status = '绑定成功，已登录账号：' + email;
        await LocalStore.shared().putString('email', email.length > 0 ? email : this.email);
        return;
      }
      if (payload.pairingURL.length > 0) {
        this.status = '检测到网页健康配对二维码，正在上传…';
        const report = await this.syncHealthPairing(payload);
        this.syncStatus = report.message;
        this.status = report.message;
        return;
      }
      this.status = '未识别到有效的 EviLife 配对内容';
    } catch (err) {
      const scanError = err as BusinessError;
      if (scanError.code === 1000500002) {
        this.status = '已取消扫码';
      } else {
        this.status = ApiClient.errorMessage(err as Error);
      }
    } finally {
      this.busy = false;
    }
  }

  async bindWithCode(): Promise<void> {
    const code = this.pairingCode.trim();
    if (code.length === 0) {
      this.status = '请输入配对码';
      return;
    }
    this.busy = true;
    this.status = '正在绑定…';
    try {
      const email = await HealthSyncService.claimDevicePairing(code);
      this.logged = true;
      this.status = '绑定成功，已登录账号：' + email;
      await LocalStore.shared().putString('email', email.length > 0 ? email : this.email);
    } catch (err) {
      this.status = ApiClient.errorMessage(err as Error);
    } finally {
      this.busy = false;
    }
  }

  async syncHealth(): Promise<void> {
    this.busy = true;
    this.syncStatus = '正在检查 Health Kit 配置…';
    try {
      this.syncStatus = HealthSyncService.healthKitStatus();
      this.status = '健康数据同步需要先完成 Health Kit 配置，详见 harmony/EviLifeHarmony/README.md';
    } finally {
      this.busy = false;
    }
  }

  private async syncHealthPairing(payload: PairingPayload): Promise<SyncReport> {
    // 接入 Health Kit 后，在这里把读到的步数/睡眠/心率映射为 HealthObservation 列表；
    // 当前 SDK 未安装，先返回配置提示。
    const observations: HealthObservation[] = [];
    return await HealthSyncService.completePairing(payload.pairingURL, payload.token, observations);
  }

  @Builder
  tabBarItem(label: string, index: number) {
    Column() {
      Text(label)
        .fontSize(11)
        .fontWeight(this.tab === index ? FontWeight.Bold : FontWeight.Normal)
        .fontColor(this.tab === index ? BRAND_COLOR : SUBTEXT_COLOR)
    }
    .layoutWeight(1)
    .justifyContent(FlexAlign.Center)
    .onClick(() => {
      this.tab = index;
    })
  }

  @Builder
  loginView() {
    Column() {
      Column() {
        Text('欢迎使用 EviLife')
          .fontSize(24)
          .fontWeight(FontWeight.Bold)
          .fontColor(TEXT_COLOR)
        Text('登录或注册以同步你的健康数据')
          .fontSize(14)
          .fontColor(SUBTEXT_COLOR)
          .margin({ top: 6 })

        TextInput({ placeholder: '邮箱', text: this.email })
          .onChange((value: string) => {
            this.email = value;
          })
          .fontSize(16)
          .backgroundColor('#F7F7F9')
          .borderRadius(12)
          .margin({ top: 20 })
        TextInput({ placeholder: '密码', text: this.password })
          .type(InputType.Password)
          .onChange((value: string) => {
            this.password = value;
          })
          .fontSize(16)
          .backgroundColor('#F7F7F9')
          .borderRadius(12)
          .margin({ top: 12 })

        Button('登录')
          .width('100%')
          .height(46)
          .backgroundColor(BRAND_COLOR)
          .fontColor(Color.White)
          .borderRadius(12)
          .margin({ top: 20 })
          .enabled(!this.busy)
          .onClick(() => {
            this.login();
          })
        Button('注册新账号')
          .width('100%')
          .height(46)
          .backgroundColor(Color.White)
          .fontColor(BRAND_COLOR)
          .borderRadius(12)
          .margin({ top: 10 })
          .enabled(!this.busy)
          .onClick(() => {
            this.register();
          })

        if (this.status.length > 0) {
          Text(this.status)
            .fontSize(13)
            .fontColor(this.busy ? SUBTEXT_COLOR : DANGER_COLOR)
            .margin({ top: 14 })
            .textAlign(TextAlign.Center)
            .width('100%')
        }
      }
      .width('100%')
      .padding(24)
      .backgroundColor(CARD_COLOR)
      .borderRadius(18)
      .shadow({ radius: 12, color: 'rgba(0,0,0,0.06)', offsetY: 4 })
    }
    .width('100%')
    .layoutWeight(1)
    .justifyContent(FlexAlign.Center)
    .padding({ left: 20, right: 20, bottom: 40 })
  }

  @Builder
  chatView() {
    Column() {
      Scroll() {
        Column() {
          if (this.answer.length > 0) {
            Column() {
              Text(this.answer)
                .fontSize(15)
                .fontColor(TEXT_COLOR)
                .lineHeight(22)
            }
            .width('100%')
            .padding(18)
            .backgroundColor(CARD_COLOR)
            .borderRadius(16)
          } else {
            Column() {
              Text('循证问答')
                .fontSize(18)
                .fontWeight(FontWeight.Medium)
                .fontColor(TEXT_COLOR)
              Text('提出健康问题，EviLife 会检索证据并给出分级回答。')
                .fontSize(13)
                .fontColor(SUBTEXT_COLOR)
                .margin({ top: 6 })
            }
            .width('100%')
            .padding(18)
            .backgroundColor(CARD_COLOR)
            .borderRadius(16)
          }
          if (this.status.length > 0) {
            Text(this.status)
              .fontSize(13)
              .fontColor(SUBTEXT_COLOR)
              .margin({ top: 12 })
          }
        }
        .width('100%')
      }
      .scrollBar(BarState.Off)
      .layoutWeight(1)
      .padding({ left: 20, right: 20, top: 4, bottom: 12 })

      Column() {
        TextArea({ placeholder: '想问什么？', text: this.question })
          .onChange((value: string) => {
            this.question = value;
          })
          .height(90)
          .fontSize(15)
          .backgroundColor('#F7F7F9')
          .borderRadius(12)
        Button('发送')
          .width('100%')
          .height(44)
          .backgroundColor(BRAND_COLOR)
          .fontColor(Color.White)
          .borderRadius(12)
          .margin({ top: 10 })
          .enabled(!this.busy)
          .onClick(() => {
            this.ask();
          })
      }
      .padding({ left: 20, right: 20, bottom: 12 })
    }
    .width('100%')
    .layoutWeight(1)
  }

  @Builder
  healthView() {
    Scroll() {
      Column() {
        Column() {
          Text('扫码绑定网页账号')
            .fontSize(17)
            .fontWeight(FontWeight.Medium)
            .fontColor(TEXT_COLOR)
          Text('扫描网页「健康档案」页面的配对二维码，或输入 6 位配对码，把手机绑定到该账号。')
            .fontSize(13)
            .fontColor(SUBTEXT_COLOR)
            .lineHeight(19)
            .margin({ top: 6 })
          Button('打开相机扫码')
            .width('100%')
            .height(44)
            .backgroundColor(BRAND_COLOR)
            .fontColor(Color.White)
            .borderRadius(12)
            .margin({ top: 14 })
            .enabled(!this.busy)
            .onClick(() => {
              this.scanToBind();
            })
          Row() {
            TextInput({ placeholder: '输入配对码', text: this.pairingCode })
              .onChange((value: string) => {
                this.pairingCode = value;
              })
              .layoutWeight(1)
              .height(40)
              .fontSize(14)
              .backgroundColor('#F7F7F9')
              .borderRadius(10)
            Button('绑定')
              .height(40)
              .padding({ left: 18, right: 18 })
              .backgroundColor(BRAND_SOFT_COLOR)
              .fontColor(BRAND_COLOR)
              .borderRadius(10)
              .margin({ left: 10 })
              .enabled(!this.busy)
              .onClick(() => {
                this.bindWithCode();
              })
          }
          .margin({ top: 12 })
        }
        .width('100%')
        .padding(18)
        .backgroundColor(CARD_COLOR)
        .borderRadius(16)
        .margin({ top: 4 })

        Column() {
          Text('华为健康数据同步')
            .fontSize(17)
            .fontWeight(FontWeight.Medium)
            .fontColor(TEXT_COLOR)
          Text('通过华为 Health Kit（运动健康）授权读取步数、睡眠、心率等数据并同步到 EviLife。')
            .fontSize(13)
            .fontColor(SUBTEXT_COLOR)
            .lineHeight(19)
            .margin({ top: 6 })
          Button('授权并同步健康数据')
            .width('100%')
            .height(44)
            .backgroundColor(BRAND_SOFT_COLOR)
            .fontColor(BRAND_COLOR)
            .borderRadius(12)
            .margin({ top: 14 })
            .enabled(!this.busy)
            .onClick(() => {
              this.syncHealth();
            })
          if (this.syncStatus.length > 0) {
            Text(this.syncStatus)
              .fontSize(13)
              .fontColor(SUBTEXT_COLOR)
              .lineHeight(19)
              .margin({ top: 10 })
          }
        }
        .width('100%')
        .padding(18)
        .backgroundColor(CARD_COLOR)
        .borderRadius(16)
        .margin({ top: 14 })

        if (this.status.length > 0) {
          Text(this.status)
            .fontSize(13)
            .fontColor(SUBTEXT_COLOR)
            .margin({ top: 14 })
            .textAlign(TextAlign.Center)
            .width('100%')
        }
      }
      .width('100%')
      .padding({ left: 20, right: 20, top: 4, bottom: 16 })
    }
    .scrollBar(BarState.Off)
    .layoutWeight(1)
  }

  @Builder
  settingsView() {
    Scroll() {
      Column() {
        Column() {
          Text('服务器地址')
            .fontSize(17)
            .fontWeight(FontWeight.Medium)
            .fontColor(TEXT_COLOR)
          TextInput({ placeholder: 'http://192.168.1.100:8010', text: this.server })
            .onChange((value: string) => {
              this.server = value;
            })
            .fontSize(15)
            .backgroundColor('#F7F7F9')
            .borderRadius(12)
            .margin({ top: 12 })
          Button('保存服务器地址')
            .width('100%')
            .height(44)
            .backgroundColor(BRAND_COLOR)
            .fontColor(Color.White)
            .borderRadius(12)
            .margin({ top: 14 })
            .onClick(() => {
              this.saveServer();
            })
        }
        .width('100%')
        .padding(18)
        .backgroundColor(CARD_COLOR)
        .borderRadius(16)
        .margin({ top: 4 })

        Column() {
          Row() {
            Text('当前账号')
              .fontSize(15)
              .fontColor(TEXT_COLOR)
            Blank()
            Text(this.email.length > 0 ? this.email : '未登录')
              .fontSize(14)
              .fontColor(SUBTEXT_COLOR)
          }
          .width('100%')
          .height(46)
          Row() {
            Text('退出登录')
              .fontSize(15)
              .fontColor(DANGER_COLOR)
            Blank()
          }
          .width('100%')
          .height(46)
          .onClick(() => {
            this.logout();
          })
        }
        .width('100%')
        .padding({ left: 18, right: 18 })
        .backgroundColor(CARD_COLOR)
        .borderRadius(16)
        .margin({ top: 14 })

        if (this.status.length > 0) {
          Text(this.status)
            .fontSize(13)
            .fontColor(SUBTEXT_COLOR)
            .margin({ top: 14 })
        }
      }
      .width('100%')
      .padding({ left: 20, right: 20, top: 4, bottom: 16 })
    }
    .scrollBar(BarState.Off)
    .layoutWeight(1)
  }

  build() {
    Column() {
      Column() {
        Text('EviLife')
          .fontSize(30)
          .fontWeight(FontWeight.Bold)
          .fontColor(TEXT_COLOR)
      }
      .width('100%')
      .padding({ left: 20, right: 20, top: 8, bottom: 12 })
      .alignItems(HorizontalAlign.Start)

      if (!this.logged) {
        this.loginView()
      } else if (this.tab === 0) {
        this.chatView()
      } else if (this.tab === 1) {
        this.healthView()
      } else {
        this.settingsView()
      }

      if (this.logged) {
        Row() {
          this.tabBarItem('问答', 0)
          this.tabBarItem('健康', 1)
          this.tabBarItem('设置', 2)
        }
        .width('100%')
        .height(56)
        .backgroundColor(CARD_COLOR)
        .border({ width: { top: 0.5 }, color: BORDER_COLOR })
      }
    }
    .width('100%')
    .height('100%')
    .backgroundColor(BG_COLOR)
  }
}

