import React, { useEffect, useState } from 'react';
import type { Task } from './api/types';
import { restClient } from './api/restClient';
import { mcpClient } from './api/mcpClient';
import { Navbar, type NavTab } from './components/Navbar';
import { TaskModal } from './components/TaskModal';
import { Dashboard } from './pages/Dashboard';
import { AllTasks } from './pages/AllTasks';
import { PriorityAnalysis } from './pages/PriorityAnalysis';
import { RecoveryCenter } from './pages/RecoveryCenter';
import { AssistantSimulation } from './pages/AssistantSimulation';
import './styles/theme.css';

export function App() {
  const [activeTab, setActiveTab] = useState<NavTab>('dashboard');
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [mcpConnected, setMcpConnected] = useState<boolean>(false);
  const [mcpToolsCount, setMcpToolsCount] = useState<number>(0);

  const fetchTasks = async () => {
    try {
      const data = await restClient.listTasks();
      setTasks(data);
    } catch (err) {
      console.error('Failed to load tasks:', err);
    }
  };

  useEffect(() => {
    fetchTasks();

    // Check MCP connectivity
    mcpClient
      .connect()
      .then(({ tools }) => {
        setMcpConnected(true);
        setMcpToolsCount(tools.length);
      })
      .catch(() => {
        setMcpConnected(false);
      });
  }, []);

  const handleSaveTask = async (data: any) => {
    await restClient.createTask(data);
    await fetchTasks();
  };

  return (
    <div className="app-container">
      <Navbar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        mcpConnected={mcpConnected}
        mcpToolsCount={mcpToolsCount}
      />

      <main className="main-content">
        {activeTab === 'dashboard' && (
          <Dashboard
            tasks={tasks}
            onOpenCreate={() => setIsModalOpen(true)}
            onNavigateToRecovery={() => setActiveTab('recovery')}
          />
        )}

        {activeTab === 'tasks' && (
          <AllTasks
            tasks={tasks}
            onRefresh={fetchTasks}
            onOpenCreate={() => setIsModalOpen(true)}
          />
        )}

        {activeTab === 'priority' && <PriorityAnalysis tasks={tasks} />}

        {activeTab === 'recovery' && (
          <RecoveryCenter tasks={tasks} onRefreshTasks={fetchTasks} />
        )}

        {activeTab === 'assistant' && (
          <AssistantSimulation tasks={tasks} onRefreshTasks={fetchTasks} />
        )}
      </main>

      <TaskModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSave={handleSaveTask}
        allTasks={tasks}
      />
    </div>
  );
}

export default App;
