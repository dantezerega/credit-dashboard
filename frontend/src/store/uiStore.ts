import { create } from 'zustand'

interface UiState {
  searchOpen: boolean
  filtersOpen: boolean
  tableDetailed: boolean
  setSearchOpen: (open: boolean) => void
  toggleFilters: () => void
  toggleTableDetailed: () => void
}

export const useUiStore = create<UiState>((set) => ({
  searchOpen: false,
  filtersOpen: true,
  tableDetailed: false,
  setSearchOpen: (open) => set({ searchOpen: open }),
  toggleFilters: () => set((s) => ({ filtersOpen: !s.filtersOpen })),
  toggleTableDetailed: () => set((s) => ({ tableDetailed: !s.tableDetailed })),
}))
