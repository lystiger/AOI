import { useCallback, useEffect, useRef, useState } from 'react'

import {
  DEFAULT_IMAGE_ID,
  DISMISSED_SETUP_STORAGE_KEY,
  INDUSTRIAL_THEME_STORAGE_KEY,
  SELECTED_IMAGE_STORAGE_KEY,
  SELECTED_RUN_STORAGE_KEY,
  ZEN_MODE_STORAGE_KEY,
} from '../app/constants'

function readSelectedImageForRun(runId) {
  if (typeof window === 'undefined' || !runId) {
    return DEFAULT_IMAGE_ID
  }
  try {
    const rawValue = window.localStorage.getItem(SELECTED_IMAGE_STORAGE_KEY)
    const savedSelections = rawValue ? JSON.parse(rawValue) : {}
    return savedSelections[runId] || DEFAULT_IMAGE_ID
  } catch {
    return DEFAULT_IMAGE_ID
  }
}

export function useWorkspacePrefs(effectiveSelectedImageId) {
  const [selectedRunId, setSelectedRunId] = useState(() => {
    if (typeof window === 'undefined') {
      return null
    }
    return window.localStorage.getItem(SELECTED_RUN_STORAGE_KEY)
  })
  const [selectedImageId, setSelectedImageId] = useState(() => {
    if (typeof window === 'undefined') {
      return DEFAULT_IMAGE_ID
    }
    try {
      const selectedRun = window.localStorage.getItem(SELECTED_RUN_STORAGE_KEY)
      const rawValue = window.localStorage.getItem(SELECTED_IMAGE_STORAGE_KEY)
      if (!selectedRun || !rawValue) {
        return DEFAULT_IMAGE_ID
      }
      const savedSelections = JSON.parse(rawValue)
      return savedSelections[selectedRun] || DEFAULT_IMAGE_ID
    } catch {
      return DEFAULT_IMAGE_ID
    }
  })
  const [dismissedSetupRuns, setDismissedSetupRuns] = useState(() => {
    if (typeof window === 'undefined') {
      return {}
    }
    try {
      const rawValue = window.localStorage.getItem(DISMISSED_SETUP_STORAGE_KEY)
      return rawValue ? JSON.parse(rawValue) : {}
    } catch {
      return {}
    }
  })
  const [isRunRailOpen, setIsRunRailOpen] = useState(true)
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const [isFiltersOpen, setIsFiltersOpen] = useState(true)
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [isZenMode, setIsZenMode] = useState(() => {
    if (typeof window === 'undefined') {
      return false
    }
    return window.localStorage.getItem(ZEN_MODE_STORAGE_KEY) === 'true'
  })
  const [isIndustrialTheme, setIsIndustrialTheme] = useState(() => {
    if (typeof window === 'undefined') {
      return true
    }
    const rawValue = window.localStorage.getItem(INDUSTRIAL_THEME_STORAGE_KEY)
    if (rawValue == null) {
      return true
    }
    return rawValue !== 'false'
  })
  const [hudGhostOpacity, setHudGhostOpacity] = useState(0.2)
  const [isKbNavEnabled, setIsKbNavEnabled] = useState(true)
  const [kbNavSensitivity, setKbNavSensitivity] = useState(1.0)
  const fileInputRef = useRef(null)

  const selectRun = useCallback((nextRunId) => {
    setSelectedRunId(nextRunId)
    setSelectedImageId(readSelectedImageForRun(nextRunId))
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    if (selectedRunId) {
      window.localStorage.setItem(SELECTED_RUN_STORAGE_KEY, selectedRunId)
      return
    }
    window.localStorage.removeItem(SELECTED_RUN_STORAGE_KEY)
  }, [selectedRunId])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    window.localStorage.setItem(DISMISSED_SETUP_STORAGE_KEY, JSON.stringify(dismissedSetupRuns))
  }, [dismissedSetupRuns])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    window.localStorage.setItem(INDUSTRIAL_THEME_STORAGE_KEY, String(isIndustrialTheme))
  }, [isIndustrialTheme])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    window.localStorage.setItem(ZEN_MODE_STORAGE_KEY, String(isZenMode))
  }, [isZenMode])

  useEffect(() => {
    if (typeof window === 'undefined' || !selectedRunId) {
      return
    }
    try {
      const rawValue = window.localStorage.getItem(SELECTED_IMAGE_STORAGE_KEY)
      const savedSelections = rawValue ? JSON.parse(rawValue) : {}
      const nextSelections =
        effectiveSelectedImageId === DEFAULT_IMAGE_ID
          ? Object.fromEntries(Object.entries(savedSelections).filter(([runId]) => runId !== selectedRunId))
          : { ...savedSelections, [selectedRunId]: effectiveSelectedImageId }
      window.localStorage.setItem(SELECTED_IMAGE_STORAGE_KEY, JSON.stringify(nextSelections))
    } catch {
      // Ignore localStorage write failures and keep the UI responsive.
    }
  }, [effectiveSelectedImageId, selectedRunId])

  return {
    dismissedSetupRuns,
    fileInputRef,
    hudGhostOpacity,
    isFiltersOpen,
    isIndustrialTheme,
    isKbNavEnabled,
    isRunRailOpen,
    isSettingsOpen,
    isSidebarOpen,
    isZenMode,
    kbNavSensitivity,
    selectedImageId,
    selectedRunId,
    selectRun,
    setDismissedSetupRuns,
    setHudGhostOpacity,
    setIsFiltersOpen,
    setIsIndustrialTheme,
    setIsKbNavEnabled,
    setIsRunRailOpen,
    setIsSettingsOpen,
    setIsSidebarOpen,
    setIsZenMode,
    setKbNavSensitivity,
    setSelectedImageId,
  }
}
