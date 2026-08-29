export class PairingPayload {
  code: string;
  baseURL: string;
  pairingURL: string;
  token: string;
  connectorID: string;

  constructor(code: string, baseURL: string, pairingURL: string, token: string, connectorID: string) {
    this.code = code;
    this.baseURL = baseURL;
    this.pairingURL = pairingURL;
    this.token = token;
    this.connectorID = connectorID;
  }
}

/**
 * 与 iOS PairingParser 对齐的扫码内容解析：
 * 0. 团队协议 JSON：{"pairing_url": "...", "token": "...", "connector_id": "..."}
 * 1. EviLife 配对 JSON：{"code": "ABC123", "base_url": "..."}
 * 2. URL 带 code 参数：https://host/pair?code=ABC123
 * 3. URL 最后一段是配对码：https://host/pair/TDCDV8
 * 4. 原始配对码（4–16 位字母数字）
 */
export class PairingParser {
  static parse(raw: string): PairingPayload | null {
    const trimmed = raw.trim();
    if (trimmed.length === 0) {
      return null;
    }

    const json = PairingParser.tryParseJson(trimmed);
    if (json !== null) {
      const pairingURL = PairingParser.str(json['pairing_url']);
      if (pairingURL.length > 0) {
        return new PairingPayload(
          '',
          '',
          pairingURL,
          PairingParser.str(json['token']),
          PairingParser.str(json['connector_id'])
        );
      }
      const code = PairingParser.normalize(PairingParser.str(json['code']));
      if (code.length > 0) {
        return new PairingPayload(code, PairingParser.str(json['base_url']), '', '', '');
      }
    }

    const codeMatch = /[?&]code=([^&#\s]+)/.exec(trimmed);
    if (codeMatch !== null && codeMatch.length >= 2) {
      const code = PairingParser.normalize(decodeURIComponent(codeMatch[1]));
      if (code.length > 0) {
        return new PairingPayload(code, PairingParser.baseOf(trimmed), '', '', '');
      }
    }

    const urlMatch = /^(https?|evilife):\/\/[^\s]+$/.exec(trimmed);
    if (urlMatch !== null) {
      const last = PairingParser.normalize(trimmed.substring(trimmed.lastIndexOf('/') + 1));
      if (last.length >= 4 && last.length <= 16) {
        return new PairingPayload(last, PairingParser.baseOf(trimmed), '', '', '');
      }
    }

    const cleaned = PairingParser.normalize(trimmed);
    if (cleaned.length >= 4 && cleaned.length <= 16) {
      return new PairingPayload(cleaned, '', '', '', '');
    }

    return null;
  }

  private static tryParseJson(text: string): Record<string, Object> | null {
    try {
      const parsed = JSON.parse(text) as Record<string, Object>;
      if (parsed === null) {
        return null;
      }
      return parsed;
    } catch (err) {
      return null;
    }
  }

  private static str(value: Object | undefined): string {
    return typeof value === 'string' ? value : '';
  }

  private static normalize(value: string): string {
    let result = '';
    const upper = value.toUpperCase();
    for (let i = 0; i < upper.length; i++) {
      const code = upper.charCodeAt(i);
      const isAlnum = (code >= 48 && code <= 57) || (code >= 65 && code <= 90);
      if (isAlnum) {
        result += upper.charAt(i);
      }
    }
    return result;
  }

  private static baseOf(text: string): string {
    const schemeEnd = text.indexOf('://');
    if (schemeEnd < 0) {
      return '';
    }
    const rest = text.substring(schemeEnd + 3);
    const slash = rest.indexOf('/');
    const hostPart = slash >= 0 ? rest.substring(0, slash) : rest;
    const colon = hostPart.indexOf(':');
    const host = colon >= 0 ? hostPart.substring(0, colon) : hostPart;
    if (host.length === 0) {
      return '';
    }
    const port = colon >= 0 ? hostPart.substring(colon + 1) : '';
    return port.length > 0
      ? text.substring(0, schemeEnd) + '://' + host + ':' + port
      : text.substring(0, schemeEnd) + '://' + host;
  }
}
