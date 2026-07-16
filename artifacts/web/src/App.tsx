import { useState } from "react";
import { MenuIcon, Settings2Icon } from "lucide-react";
import { Sidebar } from "@/components/chat/Sidebar";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { AuroraAvatar } from "@/components/chat/AuroraAvatar";
import { ConversationSettingsPanel } from "@/components/chat/ConversationSettingsPanel";
import { useChat } from "@/hooks/useChat";
import { useAuroraAvatar } from "@/hooks/useAuroraAvatar";
import { useConversationPreferences } from "@/hooks/useConversationPreferences";
import {
  ConversationPreferencesContext,
  conversationPersonalizationEnabled,
} from "@/lib/conversationPersonalization";

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const {
    sessions,
    activeId,
    activeSession,
    loading,
    createSession,
    selectSession,
    deleteSession,
    renameSession,
    togglePinSession,
    sendMessage,
    refreshLiveMatch,
    lockLiveContext,
  } = useChat();
  const { avatarUrl, setFromFile, clear } = useAuroraAvatar();
  const { preferences, setPreferences } = useConversationPreferences();

  const handleNewChat = () => {
    createSession();
    setSidebarOpen(false);
  };

  const handleSelect = (id: string) => {
    selectSession(id);
    setSidebarOpen(false);
  };

  return (
    <ConversationPreferencesContext.Provider value={preferences}>
      <div className="flex h-screen overflow-hidden bg-[#0f0f0f] text-[#ECECEC] antialiased">
        <Sidebar
          sessions={sessions}
          activeId={activeId}
          avatarUrl={avatarUrl}
          onSelect={handleSelect}
          onNewChat={handleNewChat}
          onDelete={deleteSession}
          onRename={renameSession}
          onTogglePin={togglePinSession}
          onAvatarUpload={async (file) => {
            await setFromFile(file);
          }}
          onAvatarClear={clear}
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          collapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed((v) => !v)}
        />

        <main className="flex min-w-0 flex-1 flex-col overflow-hidden bg-[#0f0f0f]">
          <header className="flex h-12 shrink-0 items-center gap-3 bg-[#0f0f0f] px-3 md:px-5">
            <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              className="rounded-lg p-2 text-[#A0A0A0] hover:bg-white/5 hover:text-[#ECECEC] md:hidden"
              aria-label="Abrir menu"
            >
              <MenuIcon size={18} />
            </button>

            {/* [Avatar Aurora] ⚙️ — gear only when feature flag is true */}
            <div className="flex min-w-0 items-center gap-1.5">
              <div className="flex min-w-0 items-center gap-2.5">
                <AuroraAvatar url={avatarUrl} size="sm" className="md:hidden" />
                <p className="truncate text-[0.875rem] font-medium tracking-[-0.01em] text-[#ECECEC]/90">
                  Aurora
                </p>
              </div>
              {conversationPersonalizationEnabled ? (
                <button
                  type="button"
                  onClick={() => setSettingsOpen(true)}
                  className="shrink-0 rounded-lg p-2 text-[#A0A0A0] transition-colors hover:bg-white/5 hover:text-[#ECECEC]"
                  aria-label="Personalizar Aurora"
                  title="Personalizar Aurora"
                >
                  <Settings2Icon size={16} />
                </button>
              ) : null}
            </div>
          </header>

          <ChatWindow
            session={activeSession}
            loading={loading}
            avatarUrl={avatarUrl}
            onSend={sendMessage}
            onRefreshLiveMatch={refreshLiveMatch}
            onLockLiveContext={lockLiveContext}
          />
        </main>

        {conversationPersonalizationEnabled ? (
          <ConversationSettingsPanel
            open={settingsOpen}
            onOpenChange={setSettingsOpen}
            preferences={preferences}
            onChange={setPreferences}
          />
        ) : null}
      </div>
    </ConversationPreferencesContext.Provider>
  );
}
