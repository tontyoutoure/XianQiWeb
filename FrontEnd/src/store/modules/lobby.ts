// store/modules/lobby.ts
import { ActionContext } from 'vuex'

interface Lobby {
  id: string
  host: string
  players: string[]
  chip_count?: number
  max_players: number
}

interface LobbyState {
  lobbies: Lobby[]
}

interface RootState {
  lobby: LobbyState
  user: {
    playerName: string
  }
}

type LobbyActionContext = ActionContext<LobbyState, RootState>

export const lobby = {
  namespaced: true,

  state: (): LobbyState => ({
    lobbies: []
  }),

  mutations: {
    SET_LOBBIES(state: LobbyState, lobbies: Lobby[]) {
      state.lobbies = lobbies
    },
    UPDATE_LOBBY(state: LobbyState, updatedLobby: Lobby) {
      const index = state.lobbies.findIndex(l => l.id === updatedLobby.id)
      if (index !== -1) {
        state.lobbies[index] = updatedLobby
      }
    },
    ADD_LOBBY(state: LobbyState, lobby: Lobby) {
      state.lobbies.push(lobby)
    },
    REMOVE_LOBBY(state: LobbyState, lobbyId: string) {
      state.lobbies = state.lobbies.filter(l => l.id !== lobbyId)
    }
  },

  actions: {
    async fetchLobbies({ commit }: LobbyActionContext) {
      try {
        const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
        console.log('Fetching lobbies from:', baseUrl);
        
        const response = await fetch(`${baseUrl}/lobby/list`);
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const lobbies = await response.json();
        console.log('Received lobbies:', lobbies);
        commit('SET_LOBBIES', lobbies);
      } catch (error) {
        console.error('Failed to fetch lobbies:', error);
        throw error; // Re-throw to handle in component
      }
    },

    async createLobby({ commit, rootState }: LobbyActionContext, chipCount: number) {
      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      console.log('Creating lobby at:', baseUrl);
      const response = await fetch(`${baseUrl}/lobby/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          player_name: rootState.user.playerName,
          initial_chip_count: chipCount
        })
      })
      const newLobby = await response.json()
      commit('ADD_LOBBY', newLobby)
      return newLobby
    },

    async joinLobby({ commit, rootState }: LobbyActionContext, lobbyId: string) {
      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      console.log('Joining lobby at:', baseUrl, 'with ID:', lobbyId);
      
      const response = await fetch(`${baseUrl}/lobby/${lobbyId}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          player_name: rootState.user.playerName
        })
      })
      const updatedLobby = await response.json()
      commit('UPDATE_LOBBY', updatedLobby)
      return updatedLobby
    },

    async leaveLobby({ commit, rootState }: LobbyActionContext, lobbyId: string) {
      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      console.log('Leaving lobby at:', baseUrl, 'with ID:', lobbyId);
      
      const response = await fetch(`${baseUrl}/lobby/${lobbyId}/leave`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          player_name: rootState.user.playerName
        })
      })
      const result = await response.json()
      
      if (result.status === 'success' && !result.lobby) {
        commit('REMOVE_LOBBY', lobbyId)
      } else if (result.lobby) {
        commit('UPDATE_LOBBY', result.lobby)
      }
    }
  }
}
