// src/store/modules/user.ts
import { ActionContext } from 'vuex'

interface UserState {
  playerName: string;
  isReady: boolean;
  currentLobbyId: string | null;
}

interface RootState {
  user: UserState;
}

type UserActionContext = ActionContext<UserState, RootState>

export const user = {
  namespaced: true,
  
  state: (): UserState => ({
    playerName: '',
    isReady: false,
    currentLobbyId: null
  }),

  mutations: {
    SET_PLAYER_NAME(state: UserState, name: string) {
      state.playerName = name
    },
    SET_READY_STATUS(state: UserState, status: boolean) {
      state.isReady = status
    },
    SET_LOBBY_ID(state: UserState, lobbyId: string | null) {
      state.currentLobbyId = lobbyId
    }
  },

  actions: {
    setPlayerName({ commit }: UserActionContext, name: string) {
      commit('SET_PLAYER_NAME', name)
    },
    toggleReady({ commit, state }: UserActionContext) {
      commit('SET_READY_STATUS', !state.isReady)
    },
    joinLobby({ commit }: UserActionContext, lobbyId: string) {
      commit('SET_LOBBY_ID', lobbyId)
    },
    leaveLobby({ commit }: UserActionContext) {
      commit('SET_LOBBY_ID', null)
      commit('SET_READY_STATUS', false)
    }
  }
}