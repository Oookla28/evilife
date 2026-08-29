import { common } from '@kit.AbilityKit';
import { BusinessError } from '@kit.BasicServicesKit';
import { ApiClient } from '../common/ApiClient';
import { LocalStore } from '../common/LocalStore';
import { PairingParser, PairingPayload } from '../common/PairingParser';
import { ScanService } from '../common/ScanService';
import { HealthObservation, HealthSyncService, SyncReport } from '../common/HealthSyncService';
import { LifestyleService } from '../common/LifestyleService';

const BG_COLOR: string = '#F2F2F7';
const CARD_COLOR: string = '#FFFFFF';
const TEXT_COLOR: string = '#1C1C1E';
const SUBTEXT_COLOR: string = '#8E8E93';
const BRAND_COLOR: string = '#0F766E';
const BRAND_SOFT_COLOR: string = '#E6F4F1';
const BORDER_COLOR: string = '#E5E5EA';
const DANGER_COLOR: string = '#FF3B30';

/** 健康档案列表项。 */
class ObservationItem {
  id: string;
  kindText: string;
  valueText: string;
  timeText: string;

  constructor(id: string, kindText: string, valueText: string, timeText: string) {
    this.id = id;
    this.kindText = kindText;
    this.valueText = valueText;
    this.timeText = timeText;
  }
}

/** 会话历史列表项。 */
class ConversationItem {
  sessionId: string;
  title: string;
  updatedAt: string;
  messageCount: number;

  constructor(sessionId: string, title: string, updatedAt: string, messageCount: number) {
    this.sessionId = sessionId;
    this.title = title;
    this.updatedAt = updatedAt;
    this.messageCount = messageCount;
  }
}

/** 报告分析列表项。 */
class ReportItem {
  id: string;
  fileName: string;
  summary: string;
  timeText: string;

  constructor(id: string, fileName: string, summary: string, timeText: string) {
    this.id = id;
    this.fileName = fileName;
    this.summary = summary;
    this.timeText = timeText;
  }
}

@Entry
@Component
struct Index {
  @State tab: number = 0;
  @State email: string = '';
  @State password: string = '';
  @State question: string = '';
  @State server: string = 'http://192.168.43.5:8000';
  @State logged: boolean = false;
  @State status: string = '';
  @State answer: string = '';
  @State pairingCode: string = '';
  @State syncStatus: string = '';
  @State busy: boolean = false;
  @State fastGoal: string = '16';
  @State fastStatusText: string = '';
  @State activeFastId: string = '';
  @State todayText: string = '';
  @State observationItems: ObservationItem[] = [];
  @State reportItems: ReportItem[] = [];
  @State historyOpen: boolean = false;
  @State historyItems: ConversationItem[] = [];
  @State historyDetail: string = '';
  @State accountText: string = '';
  @State showRegister: boolean = false;
  @State displayName: string = '';
  @State confirmPassword: string = '';
  @State registerStatus: string = '';

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

  private validateRegister(): string {
    const email = this.email.trim();
    if (email.length === 0) {
      return '请输入邮箱';
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return '请输入有效邮箱';
    }
    const name = this.displayName.trim();
    if (name.length === 0) {
      return '请输入显示名称';
    }
    if (this.password.length < 10) {
      return '密码至少需要 10 位';
    }
    if (!/[a-zA-Z]/.test(this.password) || !/[0-9]/.test(this.password)) {
      return '密码至少包含一个字母和一个数字';
    }
    if (this.password !== this.confirmPassword) {
      return '两次输入的密码不一致';
    }
    return '';
  }

  async register(): Promise<void> {
    const invalid = this.validateRegister();
    if (invalid.length > 0) {
      this.registerStatus = invalid;
      return;
    }
    this.busy = true;
    this.registerStatus = '正在注册…';
    try {
      const body: Record<string, Object> = {
        'email': this.email.trim().toLowerCase(),
        'password': this.password,
        'display_name': this.displayName.trim()
      };
      await ApiClient.shared().postJson('/api/v1/auth/register', body);
      this.logged = true;
      this.showRegister = false;
      this.confirmPassword = '';
      this.status = '注册成功，已登录';
      await LocalStore.shared().putString('email', this.email.trim().toLowerCase());
    } catch (err) {
      this.registerStatus = ApiClient.errorMessage(err as Error);
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
        await this.loadObservations();
        this.tab = 2;
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
      await this.loadObservations();
    } catch (err) {
      this.status = ApiClient.errorMessage(err as Error);
    } finally {
      this.busy = false;
    }
  }

  async syncHealth(): Promise<void> {
    if (!this.logged) {
      this.syncStatus = '请先登录，再同步健康数据';
      return;
    }
    this.busy = true;
    this.syncStatus = '正在检查 Health Kit 配置…';
    try {
      if (HealthSyncService.healthKitConfigured()) {
        // Health Kit 已接入：读取真实数据并写入当前账号。
        this.syncStatus = '正在读取华为运动健康数据…';
        const real = await HealthSyncService.fetchRealObservations();
        if (real !== null && real.length > 0) {
          const report = await HealthSyncService.syncToDatabase(real);
          this.syncStatus = report.message;
          this.status = '已从华为运动健康同步真实数据，可在网页端「健康档案」查看';
          return;
        }
        this.syncStatus = 'Health Kit 未授权或今日暂无数据，请检查运动健康 App 与授权';
        this.status = '可在网页端「健康档案」查看此前已同步的数据';
        return;
      }
      // Health Kit SDK 未接入：写入演示观测，打通「手机 → 后端 → 数据库」链路。
      const demo = HealthSyncService.demoObservations();
      const report = await HealthSyncService.syncToDatabase(demo);
      this.syncStatus = report.message + '（演示数据）';
      this.status = '数据已入库，可在网页端「健康档案」查看；配置 Health Kit 后将自动同步真实数据';
    } catch (err) {
      this.syncStatus = ApiClient.errorMessage(err as Error);
    } finally {
      this.busy = false;
    }
  }

  private todayDateString(): string {
    const now = new Date();
    const month = (now.getMonth() + 1).toString().padStart(2, '0');
    const day = now.getDate().toString().padStart(2, '0');
    return now.getFullYear().toString() + '-' + month + '-' + day;
  }

  private displayTime(iso: Object): string {
    if (typeof iso === 'string' && iso.length >= 16) {
      return iso.substring(5, 16).replace('T', ' ');
    }
    return '';
  }

  private kindText(kind: Object): string {
    const k = typeof kind === 'string' ? kind : '';
    switch (k) {
      case 'steps':
        return '步数';
      case 'sleep_minutes':
        return '睡眠';
      case 'resting_heart_rate':
        return '静息心率';
      case 'water_ml':
        return '饮水';
      case 'weight_kg':
        return '体重';
      case 'waist_cm':
        return '腰围';
      case 'mood_score':
        return '情绪';
      case 'note':
        return '备注';
      default:
        return k;
    }
  }

  private observationValueText(item: Record<string, Object>): string {
    const kind = item['kind'];
    const value = item['value'];
    const k = typeof kind === 'string' ? kind : '';
    if (k === 'note') {
      const note = item['note'];
      return typeof note === 'string' && note.length > 0 ? note : '备注';
    }
    if (typeof value === 'number') {
      if (k === 'water_ml') {
        return value.toString() + ' ml';
      }
      if (k === 'sleep_minutes') {
        return value.toString() + ' 分钟';
      }
      if (k === 'resting_heart_rate') {
        return value.toString() + ' 次/分';
      }
      if (k === 'weight_kg') {
        return value.toString() + ' kg';
      }
      if (k === 'waist_cm') {
        return value.toString() + ' cm';
      }
      if (k === 'mood_score') {
        return value.toString() + ' / 5';
      }
      return value.toString();
    }
    return '';
  }

  async loadToday(): Promise<void> {
    if (!this.logged) {
      return;
    }
    this.fastStatusText = '加载中…';
    try {
      const raw = await LifestyleService.today(this.todayDateString());
      const fasts = raw['fasts'];
      const meals = raw['meals'];
      const observations = raw['observations'];
      this.activeFastId = '';
      let activeStarted: string = '';
      let activeGoal: number = 16;
      let completedCount: number = 0;
      if (fasts instanceof Array) {
        for (let i = 0; i < fasts.length; i++) {
          const fast = fasts[i] as Record<string, Object>;
          const status = fast['status'];
          const id = fast['id'];
          if (status === 'active' && typeof id === 'string' && this.activeFastId.length === 0) {
            this.activeFastId = id;
            const startAt = fast['start_at'];
            activeStarted = typeof startAt === 'string' ? startAt : '';
            const goal = fast['goal_hours'];
            activeGoal = typeof goal === 'number' ? goal : 16;
          } else if (status === 'completed') {
            completedCount++;
          }
        }
      }
      if (this.activeFastId.length > 0) {
        this.fastStatusText = '断食进行中：开始于 ' + this.displayTime(activeStarted) +
          '，目标 ' + activeGoal.toString() + ' 小时';
      } else {
        this.fastStatusText = '当前没有进行中的断食';
      }
      const mealCount = meals instanceof Array ? meals.length : 0;
      const obsCount = observations instanceof Array ? observations.length : 0;
      this.todayText = '今日餐食 ' + mealCount.toString() + ' 条；今日健康观察 ' + obsCount.toString() +
        ' 条；已完成断食 ' + completedCount.toString() + ' 次。';
    } catch (err) {
      this.fastStatusText = ApiClient.errorMessage(err as Error);
    }
  }

  async startFastNow(): Promise<void> {
    const goal = Number(this.fastGoal);
    if (!(goal >= 1 && goal <= 24)) {
      this.fastStatusText = '目标时长需在 1-24 小时之间';
      return;
    }
    this.busy = true;
    try {
      await LifestyleService.startFast(goal);
      this.fastStatusText = '断食已开始（目标 ' + goal.toString() + ' 小时）';
      await this.loadToday();
    } catch (err) {
      this.fastStatusText = ApiClient.errorMessage(err as Error);
    } finally {
      this.busy = false;
    }
  }

  async endFastNow(): Promise<void> {
    if (this.activeFastId.length === 0) {
      this.fastStatusText = '当前没有进行中的断食';
      return;
    }
    this.busy = true;
    try {
      await LifestyleService.endFast(this.activeFastId);
      this.activeFastId = '';
      this.fastStatusText = '断食已结束，记录已保存';
      await this.loadToday();
    } catch (err) {
      this.fastStatusText = ApiClient.errorMessage(err as Error);
    } finally {
      this.busy = false;
    }
  }

  async loadObservations(): Promise<void> {
    if (!this.logged) {
      return;
    }
    try {
      const list = await LifestyleService.observations(50);
      const items: ObservationItem[] = [];
      for (let i = 0; i < list.length; i++) {
        const item = list[i] as Record<string, Object>;
        const id = item['id'];
        if (typeof id !== 'string') {
          continue;
        }
        items.push(new ObservationItem(
          id,
          this.kindText(item['kind']),
          this.observationValueText(item),
          this.displayTime(item['observed_at'])
        ));
      }
      this.observationItems = items;
    } catch (err) {
      this.syncStatus = ApiClient.errorMessage(err as Error);
    }
  }

  async deleteObservationNow(item: ObservationItem): Promise<void> {
    this.busy = true;
    try {
      await LifestyleService.deleteObservation(item.id);
      await this.loadObservations();
      this.syncStatus = '已删除 ' + item.kindText;
    } catch (err) {
      this.syncStatus = ApiClient.errorMessage(err as Error);
    } finally {
      this.busy = false;
    }
  }

  async loadReports(): Promise<void> {
    if (!this.logged) {
      return;
    }
    try {
      const list = await LifestyleService.reports(20);
      const items: ReportItem[] = [];
      for (let i = 0; i < list.length; i++) {
        const item = list[i] as Record<string, Object>;
        const id = item['id'];
        if (typeof id !== 'string') {
          continue;
        }
        const fileName = item['file_name'];
        const summary = item['summary'];
        const created = item['created_at'];
        items.push(new ReportItem(
          id,
          typeof fileName === 'string' && fileName.length > 0 ? fileName : '报告分析',
          typeof summary === 'string' && summary.length > 0 ? summary : '暂无摘要',
          this.displayTime(created)
        ));
      }
      this.reportItems = items;
    } catch (err) {
      this.todayText = ApiClient.errorMessage(err as Error);
    }
  }

  async loadHistory(): Promise<void> {
    if (!this.logged) {
      return;
    }
    this.historyDetail = '';
    try {
      const list = await LifestyleService.conversations();
      const items: ConversationItem[] = [];
      for (let i = 0; i < list.length; i++) {
        const item = list[i] as Record<string, Object>;
        const sessionId = item['session_id'];
        if (typeof sessionId !== 'string') {
          continue;
        }
        const title = item['title'];
        const updated = item['updated_at'];
        const messages = item['messages'];
        items.push(new ConversationItem(
          sessionId,
          typeof title === 'string' && title.length > 0 ? title : '未命名会话',
          this.displayTime(updated),
          messages instanceof Array ? messages.length : 0
        ));
      }
      this.historyItems = items;
    } catch (err) {
      this.todayText = ApiClient.errorMessage(err as Error);
    }
  }

  async openConversation(item: ConversationItem): Promise<void> {
    try {
      const list = await LifestyleService.conversations();
      let detail = '';
      for (let i = 0; i < list.length; i++) {
        const conv = list[i] as Record<string, Object>;
        if (conv['session_id'] !== item.sessionId) {
          continue;
        }
        const messages = conv['messages'];
        if (messages instanceof Array) {
          const parts: string[] = [];
          for (let j = 0; j < messages.length; j++) {
            const message = messages[j] as Record<string, Object>;
            const role = message['role'];
            const content = message['content'];
            const prefix = role === 'user' ? '我：' : 'EviLife：';
            if (typeof content === 'string' && content.length > 0) {
              parts.push(prefix + content);
            }
          }
          detail = parts.join('\n\n');
        }
        break;
      }
      this.historyDetail = detail.length > 0 ? detail : '该会话暂无消息内容';
    } catch (err) {
      this.historyDetail = ApiClient.errorMessage(err as Error);
    }
  }

  async loadAccount(): Promise<void> {
    if (!this.logged) {
      return;
    }
    try {
      const raw = await LifestyleService.accountSummary();
      const user = raw['user'];
      let email: string = this.email;
      let registered: string = '';
      let lastLogin: string = '';
      if (user instanceof Object && !(user instanceof Array)) {
        const userRecord = user as Record<string, Object>;
        const userEmail = userRecord['email'];
        if (typeof userEmail === 'string' && userEmail.length > 0) {
          email = userEmail;
        }
      }
      const registeredAt = raw['registered_at'];
      const lastLoginAt = raw['last_login_at'];
      registered = typeof registeredAt === 'string' ? this.displayTime(registeredAt) : '';
      lastLogin = typeof lastLoginAt === 'string' ? this.displayTime(lastLoginAt) : '';
      this.accountText = '邮箱：' + email + (registered.length > 0 ? '\n注册时间：' + registered : '') +
        (lastLogin.length > 0 ? '\n最近登录：' + lastLogin : '');
    } catch (err) {
      this.accountText = ApiClient.errorMessage(err as Error);
    }
  }

  private async syncHealthPairing(payload: PairingPayload): Promise<SyncReport> {
    // 网页健康配对二维码：读取 Health Kit 真实数据后上传到配对账号。
    if (HealthSyncService.healthKitConfigured()) {
      const real = await HealthSyncService.fetchRealObservations();
      if (real !== null && real.length > 0) {
        return await HealthSyncService.completePairing(payload.pairingURL, payload.token, real);
      }
      return new SyncReport(0, 0, 'Health Kit 未授权或今日暂无数据，请先完成授权后重试');
    }
    return new SyncReport(0, 0, 'Health Kit 尚未接入，无法上传网页配对数据，请先完成接入');
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
      this.historyOpen = false;
      this.historyDetail = '';
      if (index === 1) {
        this.loadToday();
      } else if (index === 2) {
        this.loadObservations();
      } else if (index === 3) {
        this.loadReports();
      } else if (index === 4) {
        this.loadAccount();
      }
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
            this.showRegister = true;
            this.registerStatus = '';
            this.status = '';
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
  registerView() {
    Column() {
      Column() {
        Row() {
          Text('创建账号')
            .fontSize(22)
            .fontWeight(FontWeight.Bold)
            .fontColor(TEXT_COLOR)
          Blank()
          Button('返回登录')
            .height(34)
            .padding({ left: 14, right: 14 })
            .backgroundColor(BRAND_SOFT_COLOR)
            .fontColor(BRAND_COLOR)
            .borderRadius(10)
            .onClick(() => {
              this.showRegister = false;
              this.registerStatus = '';
            })
        }
        .width('100%')

        TextInput({ placeholder: '邮箱', text: this.email })
          .onChange((value: string) => {
            this.email = value;
          })
          .fontSize(16)
          .backgroundColor('#F7F7F9')
          .borderRadius(12)
          .margin({ top: 20 })
        TextInput({ placeholder: '显示名称', text: this.displayName })
          .onChange((value: string) => {
            this.displayName = value;
          })
          .fontSize(16)
          .backgroundColor('#F7F7F9')
          .borderRadius(12)
          .margin({ top: 12 })
        TextInput({ placeholder: '密码（至少 10 位，含字母和数字）', text: this.password })
          .type(InputType.Password)
          .onChange((value: string) => {
            this.password = value;
          })
          .fontSize(16)
          .backgroundColor('#F7F7F9')
          .borderRadius(12)
          .margin({ top: 12 })
        TextInput({ placeholder: '确认密码', text: this.confirmPassword })
          .type(InputType.Password)
          .onChange((value: string) => {
            this.confirmPassword = value;
          })
          .fontSize(16)
          .backgroundColor('#F7F7F9')
          .borderRadius(12)
          .margin({ top: 12 })

        Button('注册')
          .width('100%')
          .height(46)
          .backgroundColor(BRAND_COLOR)
          .fontColor(Color.White)
          .borderRadius(12)
          .margin({ top: 20 })
          .enabled(!this.busy)
          .onClick(() => {
            this.register();
          })

        if (this.registerStatus.length > 0) {
          Text(this.registerStatus)
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
      Row() {
        Text('循证问答')
          .fontSize(17)
          .fontWeight(FontWeight.Medium)
          .fontColor(TEXT_COLOR)
        Blank()
        Button('历史会话')
          .height(34)
          .padding({ left: 16, right: 16 })
          .backgroundColor(BRAND_SOFT_COLOR)
          .fontColor(BRAND_COLOR)
          .borderRadius(10)
          .onClick(() => {
            this.historyOpen = true;
            this.loadHistory();
          })
      }
      .width('100%')
      .padding({ left: 20, right: 20, top: 4, bottom: 8 })

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
          Text(this.logged ? '当前账号：' + this.email : '当前未绑定账号')
            .fontSize(13)
            .fontWeight(FontWeight.Medium)
            .fontColor(BRAND_COLOR)
            .margin({ top: 8 })
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

        Column() {
          Row() {
            Text('我的健康档案')
              .fontSize(17)
              .fontWeight(FontWeight.Medium)
              .fontColor(TEXT_COLOR)
            Blank()
            Button('刷新')
              .height(32)
              .padding({ left: 14, right: 14 })
              .backgroundColor(BRAND_SOFT_COLOR)
              .fontColor(BRAND_COLOR)
              .borderRadius(10)
              .onClick(() => {
                this.loadObservations();
              })
          }
          .width('100%')
          Text('与网页端「健康档案」同步，支持删除单条记录。')
            .fontSize(13)
            .fontColor(SUBTEXT_COLOR)
            .lineHeight(19)
            .margin({ top: 6 })

          if (this.observationItems.length === 0) {
            Text('暂无健康数据，点击上方「授权并同步健康数据」写入演示数据。')
              .fontSize(13)
              .fontColor(SUBTEXT_COLOR)
              .lineHeight(19)
              .margin({ top: 12 })
          } else {
            ForEach(this.observationItems, (item: ObservationItem) => {
              Row() {
                Column() {
                  Text(item.kindText)
                    .fontSize(15)
                    .fontWeight(FontWeight.Medium)
                    .fontColor(TEXT_COLOR)
                  Text(item.timeText)
                    .fontSize(12)
                    .fontColor(SUBTEXT_COLOR)
                    .margin({ top: 2 })
                }
                .alignItems(HorizontalAlign.Start)
                .layoutWeight(1)
                Text(item.valueText)
                  .fontSize(15)
                  .fontColor(TEXT_COLOR)
                  .margin({ right: 10 })
                Button('删除')
                  .height(30)
                  .padding({ left: 12, right: 12 })
                  .backgroundColor('#FFEBEE')
                  .fontColor(DANGER_COLOR)
                  .borderRadius(10)
                  .enabled(!this.busy)
                  .onClick(() => {
                    this.deleteObservationNow(item);
                  })
              }
              .width('100%')
              .padding({ top: 10, bottom: 10 })
              .border({ width: { bottom: 0.5 }, color: BORDER_COLOR })
            }, (item: ObservationItem) => item.id)
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
          if (this.accountText.length > 0) {
            Text(this.accountText)
              .fontSize(13)
              .fontColor(SUBTEXT_COLOR)
              .lineHeight(19)
              .width('100%')
              .margin({ top: 4, bottom: 10 })
          }
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

  @Builder
  todayView() {
    Scroll() {
      Column() {
        Column() {
          Text('断食计时')
            .fontSize(17)
            .fontWeight(FontWeight.Medium)
            .fontColor(TEXT_COLOR)
          Text(this.fastStatusText)
            .fontSize(13)
            .fontColor(SUBTEXT_COLOR)
            .lineHeight(19)
            .margin({ top: 8 })
          if (this.activeFastId.length === 0) {
            Row() {
              Text('目标')
                .fontSize(14)
                .fontColor(TEXT_COLOR)
              TextInput({ placeholder: '16', text: this.fastGoal })
                .onChange((value: string) => {
                  this.fastGoal = value;
                })
                .type(InputType.Number)
                .width(90)
                .height(40)
                .fontSize(14)
                .backgroundColor('#F7F7F9')
                .borderRadius(10)
                .margin({ left: 10 })
              Text('小时')
                .fontSize(14)
                .fontColor(SUBTEXT_COLOR)
                .margin({ left: 8 })
            }
            .width('100%')
            .margin({ top: 12 })
            Button('开始断食')
              .width('100%')
              .height(44)
              .backgroundColor(BRAND_COLOR)
              .fontColor(Color.White)
              .borderRadius(12)
              .margin({ top: 12 })
              .enabled(!this.busy)
              .onClick(() => {
                this.startFastNow();
              })
          } else {
            Button('结束断食')
              .width('100%')
              .height(44)
              .backgroundColor(BRAND_SOFT_COLOR)
              .fontColor(BRAND_COLOR)
              .borderRadius(12)
              .margin({ top: 12 })
              .enabled(!this.busy)
              .onClick(() => {
                this.endFastNow();
              })
          }
        }
        .width('100%')
        .padding(18)
        .backgroundColor(CARD_COLOR)
        .borderRadius(16)
        .margin({ top: 4 })

        Column() {
          Text('今日汇总')
            .fontSize(17)
            .fontWeight(FontWeight.Medium)
            .fontColor(TEXT_COLOR)
          Text(this.todayText.length > 0 ? this.todayText : '加载今日数据…')
            .fontSize(13)
            .fontColor(SUBTEXT_COLOR)
            .lineHeight(19)
            .margin({ top: 8 })
          Button('刷新')
            .width('100%')
            .height(40)
            .backgroundColor(BRAND_SOFT_COLOR)
            .fontColor(BRAND_COLOR)
            .borderRadius(12)
            .margin({ top: 12 })
            .onClick(() => {
              this.loadToday();
            })
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
  reportsView() {
    Scroll() {
      Column() {
        Column() {
          Text('医学报告分析')
            .fontSize(17)
            .fontWeight(FontWeight.Medium)
            .fontColor(TEXT_COLOR)
          Text('上传检查报告后生成的逐项分析，与网页端「报告」同步。')
            .fontSize(13)
            .fontColor(SUBTEXT_COLOR)
            .lineHeight(19)
            .margin({ top: 6 })
          Button('刷新')
            .width('100%')
            .height(40)
            .backgroundColor(BRAND_SOFT_COLOR)
            .fontColor(BRAND_COLOR)
            .borderRadius(12)
            .margin({ top: 12 })
            .onClick(() => {
              this.loadReports();
            })
        }
        .width('100%')
        .padding(18)
        .backgroundColor(CARD_COLOR)
        .borderRadius(16)
        .margin({ top: 4 })

        if (this.reportItems.length === 0) {
          Column() {
            Text('暂无报告分析记录')
              .fontSize(14)
              .fontColor(SUBTEXT_COLOR)
          }
          .width('100%')
          .padding(24)
          .margin({ top: 14 })
          .backgroundColor(CARD_COLOR)
          .borderRadius(16)
        } else {
          ForEach(this.reportItems, (item: ReportItem) => {
            Column() {
              Row() {
                Text(item.fileName)
                  .fontSize(15)
                  .fontWeight(FontWeight.Medium)
                  .fontColor(TEXT_COLOR)
                  .layoutWeight(1)
                Text(item.timeText)
                  .fontSize(12)
                  .fontColor(SUBTEXT_COLOR)
              }
              .width('100%')
              Text(item.summary)
                .fontSize(13)
                .fontColor(SUBTEXT_COLOR)
                .lineHeight(19)
                .margin({ top: 8 })
            }
            .width('100%')
            .padding(16)
            .backgroundColor(CARD_COLOR)
            .borderRadius(16)
            .margin({ top: 12 })
          }, (item: ReportItem) => item.id)
        }
      }
      .width('100%')
      .padding({ left: 20, right: 20, top: 4, bottom: 16 })
    }
    .scrollBar(BarState.Off)
    .layoutWeight(1)
  }

  @Builder
  historyView() {
    Column() {
      Row() {
        Text('历史会话')
          .fontSize(17)
          .fontWeight(FontWeight.Medium)
          .fontColor(TEXT_COLOR)
        Blank()
        Button('返回')
          .height(34)
          .padding({ left: 16, right: 16 })
          .backgroundColor(BRAND_SOFT_COLOR)
          .fontColor(BRAND_COLOR)
          .borderRadius(10)
          .onClick(() => {
            this.historyOpen = false;
            this.historyDetail = '';
          })
      }
      .width('100%')
      .padding({ left: 20, right: 20, top: 4, bottom: 8 })

      if (this.historyDetail.length > 0) {
        Scroll() {
          Column() {
            Column() {
              Text(this.historyDetail)
                .fontSize(14)
                .fontColor(TEXT_COLOR)
                .lineHeight(21)
            }
            .width('100%')
            .padding(18)
            .backgroundColor(CARD_COLOR)
            .borderRadius(16)
            .margin({ top: 4 })
          }
          .width('100%')
          .padding({ left: 20, right: 20, bottom: 16 })
        }
        .scrollBar(BarState.Off)
        .layoutWeight(1)
      } else if (this.historyItems.length === 0) {
        Column() {
          Text('暂无历史会话')
            .fontSize(14)
            .fontColor(SUBTEXT_COLOR)
        }
        .width('100%')
        .layoutWeight(1)
        .justifyContent(FlexAlign.Center)
      } else {
        Scroll() {
          Column() {
            ForEach(this.historyItems, (item: ConversationItem) => {
              Column() {
                Row() {
                  Text(item.title)
                    .fontSize(15)
                    .fontWeight(FontWeight.Medium)
                    .fontColor(TEXT_COLOR)
                    .layoutWeight(1)
                  Text(item.updatedAt)
                    .fontSize(12)
                    .fontColor(SUBTEXT_COLOR)
                }
                .width('100%')
                Text('共 ' + item.messageCount.toString() + ' 条消息，点击查看')
                  .fontSize(12)
                  .fontColor(SUBTEXT_COLOR)
                  .margin({ top: 6 })
              }
              .width('100%')
              .padding(16)
              .backgroundColor(CARD_COLOR)
              .borderRadius(16)
              .margin({ top: 10 })
              .onClick(() => {
                this.openConversation(item);
              })
            }, (item: ConversationItem) => item.sessionId)
          }
          .width('100%')
          .padding({ left: 20, right: 20, bottom: 16 })
        }
        .scrollBar(BarState.Off)
        .layoutWeight(1)
      }
    }
    .width('100%')
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
        if (this.showRegister) {
          this.registerView()
        } else {
          this.loginView()
        }
      } else if (this.historyOpen) {
        this.historyView()
      } else if (this.tab === 0) {
        this.chatView()
      } else if (this.tab === 1) {
        this.todayView()
      } else if (this.tab === 2) {
        this.healthView()
      } else if (this.tab === 3) {
        this.reportsView()
      } else {
        this.settingsView()
      }

      if (this.logged) {
        Row() {
          this.tabBarItem('问答', 0)
          this.tabBarItem('今日', 1)
          this.tabBarItem('健康', 2)
          this.tabBarItem('报告', 3)
          this.tabBarItem('设置', 4)
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

