import React, { useEffect, useRef, useState } from 'react';
import type { MCPMessage, MCPTool, RecoveryProposal, Task } from '../api/types';
import { mcpClient } from '../api/mcpClient';
import { routeUserIntent } from '../intent/intentRouter';
import {
  AlertCircle,
  Bot,
  Check,
  CheckCircle2,
  ChevronRight,
  Code2,
  Cpu,
  Flame,
  Info,
  Key,
  MessageSquare,
  Send,
  Sparkles,
  User,
  X,
} from 'lucide-react';

interface AssistantSimulationProps {
  tasks: Task[];
  onRefreshTasks: () => void;
}

export const AssistantSimulation: React.FC<AssistantSimulationProps> = ({
  tasks,
  onRefreshTasks,
}) => {
  const [messages, setMessages] = useState<MCPMessage[]>([
    {
      id: 'm-welcome',
      sender: 'assistant',
      text: "Hello! I am your RealityCheck conversational assistant simulation. I communicate with the backend using the official Model Context Protocol (MCP) over Streamable HTTP (2025-11-25). Ask me anything about your deadlines, lost hours, or recovery options.",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ]);
  const [inputText, setInputText] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [mcpReady, setMcpReady] = useState<boolean>(false);
  const [mcpTools, setMcpTools] = useState<MCPTool[]>([]);
  const [tokenInput, setTokenInput] = useState<string>(mcpClient.getToken());
  const [showConfig, setShowConfig] = useState<boolean>(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Connect to MCP on mount
  useEffect(() => {
    mcpClient
      .connect()
      .then(({ tools }) => {
        setMcpReady(true);
        setMcpTools(tools);
      })
      .catch((err) => {
        console.error('MCP connection error:', err);
        setMcpReady(false);
      });
  }, []);

  const handleUpdateToken = () => {
    mcpClient.setToken(tokenInput);
    mcpClient
      .connect()
      .then(({ tools }) => {
        setMcpReady(true);
        setMcpTools(tools);
        alert('MCP Bearer Token saved and server reconnected successfully!');
      })
      .catch((err) => {
        setMcpReady(false);
        alert(`Failed to connect with new token: ${err.message}`);
      });
  };

  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputText).trim();
    if (!text || loading) return;

    setInputText('');
    const userMsgId = `usr-${Date.now()}`;
    const newMsg: MCPMessage = {
      id: userMsgId,
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, newMsg]);
    setLoading(true);

    try {
      // 1. Intent routing (deterministic, no LLM math)
      const routed = routeUserIntent(text, tasks);

      // Assistant placeholder message with "calling" state
      const assistMsgId = `asst-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        {
          id: assistMsgId,
          sender: 'assistant',
          text: routed.explanationPrompt,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          mcpCall: {
            tool: routed.toolName,
            arguments: routed.arguments,
            status: 'calling',
          },
        },
      ]);

      // 2. Real MCP tool execution over Streamable HTTP
      const toolResult = await mcpClient.callTool(routed.toolName, routed.arguments);

      // Format readable explanation based on tool
      let readableText = '';
      let recoveryProposal: RecoveryProposal | undefined = undefined;

      if (routed.toolName === 'calculate_deadline_feasibility') {
        readableText = toolResult.feasible
          ? `✓ Feasible: "${toolResult.task_title}" can be completed on time. You need ${toolResult.required_hours_per_day.toFixed(1)} hours/day with ${toolResult.slack_hours?.toFixed(1)} hours of slack.`
          : `⚠ Infeasible: "${toolResult.task_title}" has a shortfall of ${toolResult.shortfall_hours?.toFixed(1)} hours before the deadline. ${toolResult.explanation}`;
      } else if (routed.toolName === 'generate_recovery_plan') {
        recoveryProposal = toolResult as RecoveryProposal;
        readableText = `I have generated ${toolResult.options?.length || 2} recovery options. Please review the trade-offs below and choose Accept or Reject:`;
      } else if (routed.toolName === 'record_task_completion') {
        readableText = `Task completion recorded (${toolResult.actual_hours}h actual). Category duration ratio updated: ${toolResult.explanation}`;
        onRefreshTasks();
      } else if (routed.toolName === 'generate_daily_plan') {
        readableText = `Generated daily schedule for the next ${routed.arguments.days_ahead || 14} days. Validation check: ${toolResult.validation_passed ? 'PASSED ✓' : 'FAILED ⚠'}.`;
        onRefreshTasks();
      } else if (routed.toolName === 'list_tasks') {
        readableText = `Found ${toolResult.total || 0} tasks in your portfolio database.`;
      } else if (routed.toolName === 'update_duration_estimate') {
        readableText = `Category '${toolResult.category}': ${toolResult.explanation} (Ratio: ${toolResult.ratio}x)`;
      } else {
        readableText = `MCP tool "${routed.toolName}" executed successfully.`;
      }

      // Update message with success and structured result
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistMsgId
            ? {
                ...m,
                text: readableText,
                mcpCall: {
                  tool: routed.toolName,
                  arguments: routed.arguments,
                  status: 'success',
                  rawResponse: toolResult,
                  explanation: readableText,
                },
                recoveryProposal,
              }
            : m
        )
      );

      onRefreshTasks();
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          sender: 'assistant',
          text: `MCP Protocol Error: ${err.message}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleResolveInChat = async (proposalId: string, action: 'accept' | 'reject', optionIdx: number = 0) => {
    setLoading(true);
    try {
      const res = await mcpClient.callTool('resolve_recovery_proposal', {
        proposal_id: proposalId,
        action,
        option_index: optionIdx,
      });

      const confirmMsg: MCPMessage = {
        id: `res-${Date.now()}`,
        sender: 'assistant',
        text: action === 'accept'
          ? `Recovery Option ${optionIdx + 1} accepted! Tasks updated in portfolio: ${res.tasks_modified?.join(', ') || 'All affected tasks'}.`
          : `Proposal rejected. Confirmed: NO database changes were applied.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        mcpCall: {
          tool: 'resolve_recovery_proposal',
          arguments: { proposal_id: proposalId, action, option_index: optionIdx },
          status: 'success',
          rawResponse: res,
        },
      };

      setMessages((prev) => [...prev, confirmMsg]);
      onRefreshTasks();
    } catch (err: any) {
      alert(`Error resolving proposal: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const samplePrompts = [
    'Can I finish my highest-priority task by Friday?',
    'I lost three hours today. Recalculate my plan.',
    'What must move so I can finish my exam preparation on time?',
    'Show me two recovery options and wait for my approval.',
    'I finished Literature Review in 8 hours instead of 6. Update future estimates.',
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 120px)' }}>
      {/* Header bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '1rem',
          flexWrap: 'wrap',
          gap: '0.75rem',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Cpu size={22} color="#38bdf8" />
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#fff' }}>
              Conversational MCP Assistant Simulation
            </h1>
          </div>
          <div style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '0.2rem' }}>
            <span style={{ color: '#f59e0b', fontWeight: 600 }}>Simulation Notice:</span> Runs against self-hosted MCP server over Streamable HTTP (spec 2025-11-25). Not an Amazon-certified Alexa+ add-on.
          </div>
        </div>

        <button
          className="btn btn-outline"
          style={{ fontSize: '0.8rem', padding: '0.35rem 0.75rem' }}
          onClick={() => setShowConfig(!showConfig)}
        >
          <Key size={14} />
          {showConfig ? 'Hide Config' : 'MCP Auth & Settings'}
        </button>
      </div>

      {/* Config Drawer */}
      {showConfig && (
        <div className="card" style={{ padding: '1rem', marginBottom: '1rem', backgroundColor: '#0f172a' }}>
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: '280px' }}>
              <label style={{ display: 'block', fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.25rem' }}>
                MCP Bearer Token (Authorization: Bearer &lt;token&gt;)
              </label>
              <input
                type="text"
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.45rem 0.75rem',
                  borderRadius: '6px',
                  background: '#1e293b',
                  border: '1px solid #334155',
                  color: '#fff',
                  fontFamily: 'monospace',
                  fontSize: '0.85rem',
                }}
              />
            </div>
            <button className="btn btn-primary" onClick={handleUpdateToken} style={{ alignSelf: 'flex-end' }}>
              Save & Reconnect
            </button>
          </div>
          <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: '#64748b' }}>
            Endpoint: <code>POST /mcp</code> • Protocol: <code>Streamable HTTP 2025-11-25</code> • Tools Loaded:{' '}
            <code>{mcpTools.length}</code>
          </div>
        </div>
      )}

      {/* Chat Messages Container */}
      <div
        className="card"
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          overflowY: 'auto',
          padding: '1.25rem',
          marginBottom: '1rem',
          gap: '1rem',
        }}
      >
        {messages.map((m) => (
          <div
            key={m.id}
            style={{
              display: 'flex',
              gap: '0.75rem',
              alignSelf: m.sender === 'user' ? 'flex-end' : 'flex-start',
              maxWidth: '85%',
            }}
          >
            {m.sender === 'assistant' && (
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  backgroundColor: 'rgba(99, 102, 241, 0.2)',
                  border: '1px solid rgba(99, 102, 241, 0.4)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <Bot size={18} color="#818cf8" />
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              {/* Message Bubble */}
              <div
                style={{
                  padding: '0.85rem 1.15rem',
                  borderRadius: '12px',
                  backgroundColor: m.sender === 'user' ? '#4f46e5' : '#1e293b',
                  color: '#fff',
                  border: m.sender === 'user' ? 'none' : '1px solid #334155',
                  fontSize: '0.92rem',
                }}
              >
                {m.text}
              </div>

              {/* MCP Tool Invocation Panel */}
              {m.mcpCall && (
                <div
                  style={{
                    background: '#0a0f1d',
                    border: '1px solid #334155',
                    borderRadius: '8px',
                    padding: '0.75rem',
                    fontSize: '0.8rem',
                    fontFamily: 'monospace',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: '#94a3b8', marginBottom: '0.4rem' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <Code2 size={13} color="#38bdf8" />
                      MCP Tool: <strong style={{ color: '#38bdf8' }}>{m.mcpCall.tool}</strong>
                    </span>
                    <span
                      style={{
                        color:
                          m.mcpCall.status === 'success'
                            ? '#34d399'
                            : m.mcpCall.status === 'calling'
                            ? '#fbbf24'
                            : '#f87171',
                        fontWeight: 600,
                      }}
                    >
                      {m.mcpCall.status.toUpperCase()}
                    </span>
                  </div>

                  <div style={{ color: '#64748b' }}>
                    Arguments: {JSON.stringify(m.mcpCall.arguments)}
                  </div>

                  {m.mcpCall.rawResponse && (
                    <details style={{ marginTop: '0.5rem' }}>
                      <summary style={{ cursor: 'pointer', color: '#94a3b8' }}>
                        View Raw MCP JSON-RPC Output
                      </summary>
                      <pre
                        style={{
                          marginTop: '0.35rem',
                          padding: '0.5rem',
                          background: '#020617',
                          borderRadius: '4px',
                          color: '#38bdf8',
                          maxHeight: '160px',
                          overflowY: 'auto',
                        }}
                      >
                        {JSON.stringify(m.mcpCall.rawResponse, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              )}

              {/* In-Chat Recovery Options & Approval Buttons */}
              {m.recoveryProposal && m.recoveryProposal.status === 'pending' && (
                <div
                  style={{
                    background: 'rgba(99, 102, 241, 0.08)',
                    border: '1px solid rgba(99, 102, 241, 0.3)',
                    borderRadius: '8px',
                    padding: '0.85rem',
                    marginTop: '0.35rem',
                  }}
                >
                  <div style={{ fontWeight: 600, color: '#fff', fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                    Recovery Proposal (Approval Required):
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {m.recoveryProposal.options.map((opt, oIdx) => (
                      <div
                        key={oIdx}
                        style={{
                          background: '#1e293b',
                          border: '1px solid #334155',
                          borderRadius: '6px',
                          padding: '0.6rem',
                          fontSize: '0.8rem',
                        }}
                      >
                        <div style={{ fontWeight: 600, color: '#38bdf8' }}>
                          Option {oIdx + 1}: {opt.description}
                        </div>
                        <div style={{ color: '#94a3b8', marginTop: '0.2rem' }}>
                          Trade-off: {opt.trade_offs}
                        </div>
                        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                          <button
                            className="btn btn-success"
                            style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}
                            onClick={() => handleResolveInChat(m.recoveryProposal!.proposal_id, 'accept', oIdx)}
                          >
                            <Check size={12} />
                            Accept Option {oIdx + 1}
                          </button>
                        </div>
                      </div>
                    ))}
                    <div style={{ marginTop: '0.25rem' }}>
                      <button
                        className="btn btn-outline"
                        style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem', color: '#f87171' }}
                        onClick={() => handleResolveInChat(m.recoveryProposal!.proposal_id, 'reject')}
                      >
                        <X size={12} />
                        Reject All (Change Nothing)
                      </button>
                    </div>
                  </div>
                </div>
              )}

              <span style={{ fontSize: '0.7rem', color: '#64748b', alignSelf: m.sender === 'user' ? 'flex-end' : 'flex-start' }}>
                {m.timestamp}
              </span>
            </div>

            {m.sender === 'user' && (
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  backgroundColor: '#4f46e5',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <User size={18} color="#fff" />
              </div>
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggested prompts pills */}
      <div style={{ display: 'flex', gap: '0.5rem', overflowX: 'auto', paddingBottom: '0.5rem', marginBottom: '0.5rem' }}>
        {samplePrompts.map((p, idx) => (
          <button
            key={idx}
            className="btn btn-outline"
            style={{
              fontSize: '0.75rem',
              padding: '0.3rem 0.65rem',
              whiteSpace: 'nowrap',
              borderRadius: '9999px',
            }}
            onClick={() => handleSendMessage(p)}
          >
            <Sparkles size={12} color="#38bdf8" />
            {p}
          </button>
        ))}
      </div>

      {/* Input bar */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSendMessage();
        }}
        style={{ display: 'flex', gap: '0.5rem' }}
      >
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder="Ask a question or request a plan recalculation..."
          disabled={loading}
          style={{
            flex: 1,
            padding: '0.75rem 1rem',
            borderRadius: '10px',
            background: '#1e293b',
            border: '1px solid #334155',
            color: '#fff',
            fontSize: '0.95rem',
          }}
        />
        <button
          type="submit"
          className="btn btn-primary"
          disabled={loading || !inputText.trim()}
          style={{ padding: '0 1.25rem' }}
        >
          <Send size={18} />
        </button>
      </form>
    </div>
  );
};
