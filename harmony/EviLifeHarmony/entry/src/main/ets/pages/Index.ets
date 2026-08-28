import { http } from '@kit.NetworkKit';

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

  async call(path: string, body: string): Promise<string> {
    let client = http.createHttp();
    let response = await client.request(this.server + path, { method: http.RequestMethod.POST, header: { 'Content-Type': 'application/json' }, extraData: body });
    client.destroy(); return response.result.toString();
  }
  async login(): Promise<void> { try { await this.call('/api/v1/auth/login', JSON.stringify({ email: this.email, password: this.password })); this.logged = true; this.status = '登录成功'; } catch (e) { this.status = '登录失败，请检查服务器地址'; } }
  async ask(): Promise<void> {
    if (!this.question) return;
    try {
      this.status = '正在分析…';
      let client = http.createHttp();
      let encoded = `session_id=${encodeURIComponent(Date.now().toString())}&mode=auto&text=${encodeURIComponent(this.question)}`;
      let response = await client.request(this.server + '/api/v1/orchestrate', { method: http.RequestMethod.POST, header: { 'Content-Type': 'application/x-www-form-urlencoded' }, extraData: encoded });
      this.answer = response.result.toString(); client.destroy(); this.status = '回答已生成';
    } catch (e) { this.status = '请求失败'; }
  }
  build() {
    Column() {
      Text('EviLife').fontSize(28).fontWeight(FontWeight.Bold).fontColor('#0F766E').margin({ bottom: 16 });
      if (!this.logged) { Text('登录').fontSize(22); TextInput({ placeholder: '邮箱', text: this.email }).onChange(v => this.email = v); TextInput({ placeholder: '密码', text: this.password }).type(InputType.Password).onChange(v => this.password = v); Button('登录').onClick(() => this.login()).width('100%'); Text(this.status).fontColor('#64748B'); }
      else if (this.tab === 0) { Text('循证问答').fontSize(22); TextArea({ placeholder: '想问什么？', text: this.question }).onChange(v => this.question = v).height(110); Button('发送').onClick(() => this.ask()).width('100%'); Text(this.status); if (this.answer) Text(this.answer).padding(14).backgroundColor('#F0FDFA').borderRadius(14); }
      else if (this.tab === 1) { Text('健康数据').fontSize(22); Text('鸿蒙版将通过华为运动健康/Health Kit 同步数据。').fontColor('#475569'); Button('扫码绑定网页账号').onClick(() => this.status = '请使用系统相机扫描网页配对二维码').width('100%'); Button('授权并同步健康数据').onClick(() => this.status = '请在后续版本配置 Health Kit 权限').width('100%'); Text(this.status); }
      else { Text('设置').fontSize(22); TextInput({ placeholder: '服务器地址', text: this.server }).onChange(v => this.server = v); Text('当前账号：' + this.email).fontColor('#475569'); }
      if (this.logged) Row() { ['问答', '健康', '设置'].forEach((label: string, i: number) => { Button(label).onClick(() => this.tab = i).layoutWeight(1).backgroundColor(this.tab === i ? '#CCFBF1' : '#FFFFFF'); }); }.margin({ top: 24 }).width('100%');
    }.padding(24).width('100%').height('100%').backgroundColor('#F8FAFC');
  }
}
