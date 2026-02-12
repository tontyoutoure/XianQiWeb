import { createStore } from 'vuex'
import { user } from './modules/user'
import { lobby } from './modules/lobby'

const store = createStore({
  modules: {
    user,
    lobby
  }
})

export default store