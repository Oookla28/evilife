import { preferences } from '@kit.ArkData';
import { common } from '@kit.AbilityKit';

const STORE_NAME: string = 'evilife_store';

/** 轻量本地持久化（服务器地址、登录邮箱等）。 */
export class LocalStore {
  private static instance: LocalStore | null = null;
  private pref: preferences.Preferences | null = null;

  static shared(): LocalStore {
    if (LocalStore.instance === null) {
      LocalStore.instance = new LocalStore();
    }
    return LocalStore.instance;
  }

  async init(context: common.UIAbilityContext): Promise<void> {
    if (this.pref !== null) {
      return;
    }
    this.pref = await preferences.getPreferences(context, STORE_NAME);
  }

  private ensure(): preferences.Preferences {
    if (this.pref === null) {
      throw new Error('LocalStore 未初始化');
    }
    return this.pref;
  }

  async getString(key: string, defaultValue: string): Promise<string> {
    const value = await this.ensure().get(key, defaultValue);
    return typeof value === 'string' ? value : defaultValue;
  }

  async putString(key: string, value: string): Promise<void> {
    const pref = this.ensure();
    await pref.put(key, value);
    await pref.flush();
  }

  async remove(key: string): Promise<void> {
    const pref = this.ensure();
    await pref.delete(key);
    await pref.flush();
  }
}