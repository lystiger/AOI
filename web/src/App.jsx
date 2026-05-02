import { useEffect } from 'react'
import './App.css'

import ReviewWorkspace from './components/ReviewWorkspace'
import RunRail from './components/RunRail'
import SettingsPanel from './components/SettingsPanel'
import { useToast } from './components/Toast'
import WorkspaceTopbar from './components/WorkspaceTopbar'
import { useAoiWorkspace } from './hooks/useAoiWorkspace'

function App() {
  const { fileInputRef, ...workspace } = useAoiWorkspace()
  const toast = useToast()

  useEffect(() => {
    if (workspace.error) {
      toast.error(workspace.error)
      workspace.setError('') // clear after showing toast
    }
  }, [workspace.error, toast, workspace])

  return (
    <div className="app-shell">
      <WorkspaceTopbar
        summary={workspace.summary}
        isRunRailOpen={workspace.isRunRailOpen}
        isSidebarOpen={workspace.isSidebarOpen}
        isFiltersOpen={workspace.isFiltersOpen}
        isSettingsOpen={workspace.isSettingsOpen}
        onToggleRunRail={() => workspace.setIsRunRailOpen((current) => !current)}
        onToggleSidebar={() => workspace.setIsSidebarOpen((current) => !current)}
        onToggleFilters={() => workspace.setIsFiltersOpen((current) => !current)}
        onToggleSettings={() => workspace.setIsSettingsOpen((current) => !current)}
      />

      <SettingsPanel
        isOpen={workspace.isSettingsOpen}
        onClose={() => workspace.setIsSettingsOpen(false)}
        hudGhostOpacity={workspace.hudGhostOpacity}
        onHudGhostOpacityChange={workspace.setHudGhostOpacity}
        isKbNavEnabled={workspace.isKbNavEnabled}
        onKbNavEnabledChange={workspace.setIsKbNavEnabled}
        kbNavSensitivity={workspace.kbNavSensitivity}
        onKbNavSensitivityChange={workspace.setKbNavSensitivity}
        openImagePicker={workspace.openImagePicker}
        isUploading={workspace.isUploading}
        selectedRunId={workspace.selectedRunId}
      />

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        onChange={workspace.handleImageUpload}
        hidden
        disabled={workspace.isUploading || !workspace.selectedRunId}
      />

      <main className={`workspace ${!workspace.isRunRailOpen ? 'rail-collapsed' : ''}`}>
        <RunRail workspace={workspace} />
        <ReviewWorkspace workspace={workspace} />
      </main>
    </div>
  )
}

export default App
