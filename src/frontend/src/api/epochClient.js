import axios from 'axios'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTerminalStore } from '../store/terminalStore'

const API_BASE = 'http://localhost:8000'

const getClient = () => {
    const token = useTerminalStore.getState().accessToken
    return axios.create({
        baseURL: API_BASE,
        headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
}

// QUERY HOOKS
export const useEnsembleMeta = () => {
  return useQuery({
    queryKey: ['ensembleMeta'],
    queryFn: async () => (await getClient().get('/api/ensemble/meta')).data,
    staleTime: 5 * 60 * 1000,
  })
}

export const useSignalValidation = () => {
  return useQuery({
    queryKey: ['signalValidation'],
    queryFn: async () => (await getClient().get('/api/signal/validation')).data,
    staleTime: 10 * 60 * 1000,
  })
}

export const useCausalWeights = () => {
  return useQuery({
    queryKey: ['causalWeights'],
    queryFn: async () => (await getClient().get('/api/causal/weights')).data,
    staleTime: 30 * 60 * 1000,
  })
}

export const useRetrainingReport = () => {
  return useQuery({
    queryKey: ['retrainingReport'],
    queryFn: async () => (await getClient().get('/api/retrainer/report')).data,
    staleTime: 5 * 60 * 1000,
  })
}

export const useJournal = (userId) => {
  return useQuery({
    queryKey: ['journal', userId],
    queryFn: async () => (await getClient().get(`/api/journal/${userId}`)).data,
    staleTime: 60 * 1000,
    enabled: !!userId,
  })
}

export const useEdgeProfile = (userId) => {
  return useQuery({
    queryKey: ['edgeProfile', userId],
    queryFn: async () => (await getClient().get(`/api/journal/${userId}/edge-profile`)).data,
    staleTime: 2 * 60 * 1000,
    enabled: !!userId,
  })
}

// MUTATIONS
export const useRunRetraining = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => (await getClient().post('/api/retrainer/run')).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['retrainingReport'] }),
  })
}

export const useLogJournalEntry = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (entry) => (await getClient().post('/api/journal/log', entry)).data,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['journal'] }),
  })
}

export const useRunQuantumSimulation = (gameId) => {
  const setSimulation = useTerminalStore(s => s.setSimulation)
  return useMutation({
    mutationFn: async (params) => (await getClient().post(`/api/quantum/${gameId}`, params)).data,
    onSuccess: (data) => setSimulation(data),
  })
}
