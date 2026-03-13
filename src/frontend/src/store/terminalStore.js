import { create } from 'zustand'

export const useTerminalStore = create((set) => ({
  // AUTH SLICE
  user: null,
  accessToken: null,
  isAuthenticated: false,
  login: (user, token) => set({ user, accessToken: token, isAuthenticated: true }),
  logout: () => set({ user: null, accessToken: null, isAuthenticated: false }),

  // WEBSOCKET SLICE
  wsStatus: 'disconnected',
  gameState: null,
  setWsStatus: (status) => set({ wsStatus: status }),
  setGameState: (state) => set({ gameState: state }),

  // SIGNAL SLICE
  signals: [],
  unreadCount: 0,
  addSignal: (signal) => set((state) => ({
    signals: [signal, ...state.signals].slice(0, 50),
    unreadCount: state.unreadCount + 1
  })),
  markAllRead: () => set({ unreadCount: 0 }),
  clearSignals: () => set({ signals: [] }),

  // KELLY SLICE
  currentRecommendation: null,
  bankroll: 10000,
  setBankroll: (amount) => set({ bankroll: amount }),
  setRecommendation: (rec) => set({ currentRecommendation: rec }),

  // JOURNAL SLICE
  entries: [],
  edgeProfile: null,
  addEntry: (entry) => set((state) => ({ entries: [entry, ...state.entries] })),
  setEdgeProfile: (profile) => set({ edgeProfile: profile }),

  // PROP SLICE
  propBoard: [],
  selectedPlayer: null,
  setSelectedPlayer: (player) => set({ selectedPlayer: player }),
  setPropBoard: (board) => set({ propBoard: board }),

  // ORACLE SLICE
  oracleState: null,
  adversarialHistory: [],
  setOracleState: (state) => set({ oracleState: state }),
  addAdversarialCycle: (cycle) => set((state) => ({ 
    adversarialHistory: [...state.adversarialHistory, cycle] 
  })),

  // QUANTUM SLICE
  lastSimulation: null,
  isSimulating: false,
  setSimulating: (bool) => set({ isSimulating: bool }),
  setSimulation: (result) => set({ lastSimulation: result }),

  // COMMAND SLICE
  isCommandOpen: false,
  openCommand: () => set({ isCommandOpen: true }),
  closeCommand: () => set({ isCommandOpen: false }),

  // AUDIO SLICE
  audioCtx: null,
  initAudio: () => set((state) => {
    if (state.audioCtx || typeof window === 'undefined') return {}
    return { audioCtx: new (window.AudioContext || window.webkitAudioContext)() }
  }),
  resumeAudio: async () => {
    const ctx = useTerminalStore.getState().audioCtx
    if (ctx && ctx.state === 'suspended') {
      await ctx.resume()
    }
  }
}))
