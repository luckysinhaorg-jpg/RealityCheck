import React from 'react';
import {
  Calendar,
  CheckCircle2,
  Clock,
  Cpu,
  LayoutDashboard,
  ListTodo,
  ShieldAlert,
} from 'lucide-react';

export type NavTab = 'dashboard' | 'tasks' | 'priority' | 'recovery' | 'assistant';

interface NavbarProps {
  activeTab: NavTab;
  onTabChange: (tab: NavTab) => void;
  mcpConnected: boolean;
  mcpToolsCount: number;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  onTabChange,
  mcpConnected,
  mcpToolsCount,
}) => {
  return (
    <nav className="navbar">
      <div className="brand">
        <CheckCircle2 size={24} color="#6366f1" />
        <span>RealityCheck</span>
        <span className="brand-badge">Alexa+ Track</span>
      </div>

      <div className="nav-links">
        <button
          className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => onTabChange('dashboard')}
        >
          <LayoutDashboard size={16} />
          Dashboard & Timetable
        </button>

        <button
          className={`nav-item ${activeTab === 'tasks' ? 'active' : ''}`}
          onClick={() => onTabChange('tasks')}
        >
          <ListTodo size={16} />
          All Tasks
        </button>

        <button
          className={`nav-item ${activeTab === 'priority' ? 'active' : ''}`}
          onClick={() => onTabChange('priority')}
        >
          <Clock size={16} />
          Priority Analysis
        </button>

        <button
          className={`nav-item ${activeTab === 'recovery' ? 'active' : ''}`}
          onClick={() => onTabChange('recovery')}
        >
          <ShieldAlert size={16} />
          Recovery Center
        </button>

        <button
          className={`nav-item ${activeTab === 'assistant' ? 'active' : ''}`}
          onClick={() => onTabChange('assistant')}
          style={{
            background:
              activeTab === 'assistant'
                ? 'linear-gradient(135deg, rgba(99, 102, 241, 0.4), rgba(56, 189, 248, 0.4))'
                : 'rgba(99, 102, 241, 0.1)',
            border: '1px solid rgba(99, 102, 241, 0.3)',
            color: '#fff',
          }}
        >
          <Cpu size={16} color="#38bdf8" />
          MCP Assistant Simulation
        </button>
      </div>

      <div className="mcp-pill" title="MCP over Streamable HTTP (spec 2025-11-25)">
        <span className="pulse-dot" style={{ backgroundColor: mcpConnected ? '#34d399' : '#f59e0b' }} />
        <span>MCP: {mcpConnected ? `Online (${mcpToolsCount} Tools)` : 'Connecting...'}</span>
      </div>
    </nav>
  );
};
