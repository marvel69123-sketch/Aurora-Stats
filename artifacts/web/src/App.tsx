import { useState } from "react";
import { MenuIcon } from "lucide-react";
import { Sidebar } from "@/components/chat/Sidebar";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { useChat } from "@/hooks/useChat";

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const {
    sessions,
    activeId,
    activeSession,
    loading,
    createSession,
    selectSession,
    deleteSession,
    sendMessage,
  } = useChat();

  const handleNewChat = () => {
    createSession();
    setSidebarOpen(false);
  };

  const handleSelect = (id: string) => {
    selectSession(id);
    setSidebarOpen(false);
  };

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <Sidebar
        sessions={sessions}
        activeId={activeId}
        onSelect={handleSelect}
        onNewChat={handleNewChat}
        onDelete={deleteSession}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* Main content */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {/* Mobile top bar */}
        <header className="md:hidden flex items-center gap-3 h-14 px-4 border-b border-white/[0.06] bg-background flex-shrink-0">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-2 rounded-lg text-white/40 hover:text-white/80 hover:bg-white/5 transition-colors"
          >
            <MenuIcon size={18} />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-emerald-500 flex items-center justify-center">
              <span className="text-white font-bold text-[10px]">A</span>
            </div>
            <span className="text-sm font-semibold text-white/80">Aurora</span>
          </div>
        </header>

        {/* Desktop header bar */}
        <header className="hidden md:flex items-center h-12 px-6 border-b border-white/[0.05] bg-background flex-shrink-0">
          <p className="text-xs text-white/25 truncate">
            {activeSession?.title ?? "Aurora — Inteligência Esportiva"}
          </p>
        </header>

        {/* Chat window */}
        <ChatWindow
          session={activeSession}
          loading={loading}
          onSend={sendMessage}
        />
      </div>
    </div>
  );
}
