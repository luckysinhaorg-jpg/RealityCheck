/**
 * RealityCheck MCP Client Simulation.
 *
 * Implements real Model Context Protocol (MCP) Streamable HTTP requests:
 *   - Spec: 2025-11-25
 *   - Bearer token authentication
 *   - initialize handshake
 *   - notifications/initialized notification
 *   - tools/list tool discovery
 *   - tools/call execution
 *
 * This client talks directly to the backend /mcp endpoint.
 */
import type { MCPTool } from './types';

const DEFAULT_TOKEN = 'rc_alexa_dev_token_2026_streamable_http';
const TOKEN_KEY = 'realitycheck_mcp_token';

export class MCPClient {
  private endpoint: string;
  private token: string;
  private requestId: number = 1;
  private initialized: boolean = false;
  private tools: MCPTool[] = [];
  private serverInfo: { name: string; version: string } | null = null;

  constructor(endpoint: string = '/mcp') {
    this.endpoint = endpoint;
    this.token = localStorage.getItem(TOKEN_KEY) || DEFAULT_TOKEN;
  }

  public getToken(): string {
    return this.token;
  }

  public setToken(token: string): void {
    this.token = token;
    localStorage.setItem(TOKEN_KEY, token);
    this.initialized = false;
  }

  public isInitialized(): boolean {
    return this.initialized;
  }

  public getAvailableTools(): MCPTool[] {
    return this.tools;
  }

  public getServerInfo(): { name: string; version: string } | null {
    return this.serverInfo;
  }

  /**
   * Internal JSON-RPC POST over Streamable HTTP.
   */
  private async postJsonRpc(method: string, params: Record<string, any> = {}, isNotification = false): Promise<any> {
    const id = isNotification ? undefined : this.requestId++;
    const payload: Record<string, any> = {
      jsonrpc: '2.0',
      method,
      params,
    };
    if (id !== undefined) {
      payload.id = id;
    }

    const res = await fetch(this.endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json, text/event-stream, */*',
        Authorization: `Bearer ${this.token}`,
        'Mcp-Protocol-Version': '2025-11-25',
      },
      body: JSON.stringify(payload),
    });

    if (res.status === 401) {
      throw new Error(
        'MCP Authentication Failed (401 Unauthorized). Please check your MCP Bearer Token in settings.'
      );
    }

    if (!res.ok && res.status !== 202) {
      const errText = await res.text();
      throw new Error(`MCP Request Error (${res.status}): ${errText}`);
    }

    if (res.status === 202 || isNotification) {
      return { success: true };
    }

    const data = await res.json();
    if (data.error) {
      throw new Error(data.error.message || JSON.stringify(data.error));
    }

    return data.result;
  }

  /**
   * Perform MCP protocol handshake:
   * 1. initialize
   * 2. notifications/initialized
   * 3. tools/list
   */
  public async connect(): Promise<{ serverInfo: any; tools: MCPTool[] }> {
    // 1. Handshake initialize
    const initResult = await this.postJsonRpc('initialize', {
      protocolVersion: '2025-11-25',
      capabilities: {},
      clientInfo: {
        name: 'realitycheck-browser-client',
        version: '0.1.0',
      },
    });

    this.serverInfo = initResult.serverInfo || { name: 'realitycheck', version: '0.1.0' };

    // 2. Send initialized notification
    await this.postJsonRpc('notifications/initialized', {}, true);

    // 3. List tools
    const listResult = await this.postJsonRpc('tools/list', {});
    this.tools = listResult.tools || [];
    this.initialized = true;

    return {
      serverInfo: this.serverInfo,
      tools: this.tools,
    };
  }

  /**
   * Call a tool on the MCP server via tools/call.
   */
  public async callTool(name: string, args: Record<string, any> = {}): Promise<any> {
    if (!this.initialized) {
      await this.connect();
    }

    const result = await this.postJsonRpc('tools/call', {
      name,
      arguments: args,
    });

    // MCP result has content: [{ type: "text", text: "..." }]
    if (result && Array.isArray(result.content) && result.content[0]?.text) {
      try {
        return JSON.parse(result.content[0].text);
      } catch {
        return result.content[0].text;
      }
    }

    return result;
  }
}

export const mcpClient = new MCPClient('/mcp');
