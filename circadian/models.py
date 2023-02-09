# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/00_models.ipynb.

# %% auto 0
__all__ = ['DynamicalTrajectory', 'CircadianModel', 'Forger99Model', 'Hannay19TP', 'Hannay19']

# %% ../nbs/00_models.ipynb 4
import scipy as sp
from abc import ABC, abstractmethod
import numpy as np
from scipy.signal import find_peaks
from .utils import phase_ic_guess

from ctypes import c_void_p, c_double, c_int, cdll
import scipy as sp
import pylab as plt
from pathlib import Path
import sys
from numba import jit, njit, prange
from typing import List, Tuple, Dict, Union, Optional, Callable
import time
from functools import wraps


# %% ../nbs/00_models.ipynb 8
class DynamicalTrajectory:
    """ 
    A class to store a solutions that contains both the time points and the states.
    """
    
    def __init__(self, 
                 ts: np.ndarray, # time points
                 states: np.ndarray # states at time points
                 ) -> None:
        self.ts = ts
        self.states = states
        
        
    def __call__(self, t: float) -> np.ndarray: # state of the system
        """ 
        Return the state at time t, linearly interpolated
        """
        return np.interp(t, self.ts, self.states)
    
    def __getitem__(self, idx: int) -> Tuple[float, np.ndarray]:
        return self.ts[idx], self.states[idx]
    
    def __len__(self) -> int:
        return len(self.ts)
    
    def get_batch(self,index: int) -> 'DynamicalTrajectory':
        if self.states.ndim >= 3:
            return DynamicalTrajectory(self.ts, self.states[index, :, :])
        else:
            return DynamicalTrajectory(self.ts, self.states)
        
    @property
    def batch_size(self) -> int:
        if self.states.ndim >= 3:
            return self.states.shape[0]
        else:
            return 1
    
    

# %% ../nbs/00_models.ipynb 11
class CircadianModel(ABC):
    """ Abstract base class for circadian models, defines the interface for all models """

    def __init__(self, 
                 params: dict = None # dictionary of parameters for the model, if None then the default parameters are used
                 ):
        """ Creates a new instance of the model """
        pass

    @abstractmethod
    def _default_params(self) -> dict: # dictionary of default parameters for the model:
        """
            Defines the default parameters for the model
        """
        pass
    
    @property
    def get_parameters(self)-> dict:
        """
            Returns the parameters for the model
        """
        pass
    
    def set_parameters(self, 
                       param_dict: dict # dictionary of parameters for the model)
    ) -> None:
        """
            Sets the parameters for the model
        """

        for key, value in param_dict.items():
            setattr(self, key, value)

    def step_rk4(self,
                 state: np.ndarray, #dy/dt = f(y, t)
                 light_val: float, #light value at time t in lux
                 dt=0.10 #step size in hours 
                 ):
        """
            Return the state of the model assuming a constant light value
            for one time step and using a fourth order Runga-Kutta integrator to perform the step
        """
        k1 = self.derv(state, light=light_val)
        k2 = self.derv(state + k1 * dt / 2.0, light=light_val)
        k3 = self.derv(state + k2 * dt / 2.0, light=light_val)
        k4 = self.derv(state + k3 * dt, light=light_val)
        state = state + (dt / 6.0) * (k1 + 2.0*k2 + 2.0*k3 + k4)
        return state

    def integrate_model(self,
                        ts: np.ndarray,  # Array of time points, also determines step size of RK4 solver
                        light_est: np.ndarray,  # Array of light estimates, should be the same length as ts
                        state: np.ndarray,  # Initial state of the model
                        ) -> DynamicalTrajectory:
        n = len(ts)
        sol = np.zeros((*state.shape, n))
        sol[..., 0] = state
        for idx in range(1, n):
            state = self.step_rk4(
                state=state,
                light_val=light_est[idx],
                dt=ts[idx]-ts[idx-1]
            )
            sol[..., idx] = state
        return DynamicalTrajectory(ts, sol)

    def dlmos(self, 
              trajectory: DynamicalTrajectory,  # solution from integrate_model
              ) -> np.ndarray: #array of times when the dlmo occurs for the model 
        """
            Finds the Dim Light Melatonin Onset (DLMO) markers for the model along a trajectory
        """
        pass

    def cbt(self, 
            trajectory: DynamicalTrajectory,  # solution from integrate_model
            ) -> np.ndarray: # array of times when the cbt occurs
        """
            Finds the core body temperature minumum markers for the model along a trajectory
        """
        pass

    def observer(self,
                 trajectory: np.ndarray,  # solution from integrate_model
                 observer_func: callable, # function that takes the state of the model and returns a scalar will be triggered when the sign of the function changes
                 ) -> np.array: # this will return the times when the observer func changes signs
        """ 
            Defines a generic observer for the model, this will return the times when the observer_func changes sign
        """ 
        pass

    @staticmethod
    def amplitude(state: np.ndarray, #dynamic state of the model
                  ) -> float:
        """
            Gives the amplitude of the model at a given state
        """
        pass

    @staticmethod
    def phase(state: np.ndarray #dynamic state of the model
              ) -> float:
        """
            Gives the phase of the model at a given state
        """
        pass

    @property
    def default_initial_conditions(self) -> np.ndarray:
        """
        Defines some default initial conditions for the model
        """
        pass

    def __call__(self,
                 ts: np.ndarray,  # Array of time points, also determines step size of RK4 solver
                 light_est: np.ndarray,  # Array of light estimates, should be the same length as ts
                 state: np.ndarray,  # Initial state of the model
                 *args,
                 **kwargs):
        """ Wrapper to integrate_model, can just call the model object directly """
        return self.integrate_model(ts, light_est=light_est, state=state, *args, **kwargs)

    def initial_conditions_loop(self,
                                ts: np.ndarray, #Array of time points, also determines step size of RK4 solver
                                light_est: np.ndarray, #Array of light estimates, should be the same length as ts
                                num_loops: int = 30) -> np.ndarray: 
        """ 
            Estimate the starting values by looping the given light_estimate, commonly used for to estimate the initial conditions
            assumes the individual lives the same schedule repeatedly
        """
        ic = self.default_initial_conditions
        for _ in range(num_loops):
            sol = self.integrate_model(ts, light_est, ic).states
            ic = sol[..., -1]
        return ic


# %% ../nbs/00_models.ipynb 26
class Forger99Model(CircadianModel):
    """ Implementation of the Forger 1999 model """

    def __init__(self, params: dict= None):
        """
        Create a Forger VDP model 

        This will create a model with the default parameter values as given in Hannay et al 2019.

        This class can be used to simulate and plot the results of the given light schedule on the circadian phase
        and amplitude.
        """
        # Set the parameters to the published values by default
        self._default_params()
        
        if params:
            self.set_parameters(params)
        
        
    def _default_params(self):
        """
            Use the default parameters as defined in Hannay et al 2019
        """
        
        default_params = {'taux': 24.2,
                          'mu': 0.23,
                          'G': 33.75, 
                          'alpha_0': 0.05, 
                          'delta': 0.0075,
                          'p': 0.50, 
                          'I0': 9500.0, 
                          'kparam': 0.55}

        self.set_parameters(default_params)
        
    def set_parameters(self, param_dict: dict):
        """
            Update the model parameters using a passed in parameter dictionary. Any parameters not included
            in the dictionary will be set to the default values.

            updateParameters(param_dict)

            Returns null, changes the parameters stored in the class instance
        """
        

        params = [
            'taux',
            'mu'
            'G',
            'alpha_0',
            'delta',
            'p',
            'I0', 
            'kparam']

        for key, value in param_dict.items():
            setattr(self, key, value)
            
    def get_parameters_array(self):
        """
            Return a numpy array of the models current parameters
        """
        return np.array([self.taux, 
                         self.mu, 
                         self.G, 
                         self.alpha_0, 
                         self.delta, 
                         self.p, 
                         self.I0, 
                         self.kparam ])


    def get_parameters(self):
        """Get a dictionary of the current parameters being used by the model object.

        getParameters()

        returns a dict of parameters
        """

        current_params = {
            'taux': self.taux,
            'mu': self.mu,
            'G': self.G,
            'alpha_0': self.alpha_0,
            'delta': self.delta,
            'p': self.p,
            'I0': self.I0, 
            'kparam': self.kparam}

        return (current_params)

    def alpha0(self, 
               light: float # the light value in lux
               ):
        """A helper function for modeling the light input processing"""
        return (self.alpha_0 * pow((light / self.I0), self.p))

    def derv(self, 
             y: np.ndarray, # dynamical state (x, xc, n)
             light: float # light value in lux
             ) -> np.ndarray: # This defines the ode system for the forger 99 model

        x = y[...,0]
        xc = y[...,1]
        n = y[...,2]

        Bhat = self.G * (1.0 - n) * self.alpha0(light=light) * \
            (1 - 0.4 * x) * (1 - 0.4 * xc)

        dydt = np.zeros_like(y)
        dydt[...,0] = np.pi / 12.0 * (xc + Bhat)
        dydt[...,1] = np.pi / 12.0 * (self.mu * (xc - 4.0 / 3.0 * pow(xc, 3.0)) - x * (
            pow(24.0 / (0.99669 * self.taux), 2.0) + self.kparam * Bhat))
        dydt[...,2] = 60.0 * (self.alpha0(light=light) * (1.0 - n) - self.delta * n)

        return (dydt)
    
    def cbt(self, trajectory: DynamicalTrajectory) -> np.ndarray:
        cbt_mins = find_peaks(-1*trajectory.states[0,:])[0] # min of x is the CBTmin
        return trajectory.ts[cbt_mins]
    
    def dlmos(self, trajectory: DynamicalTrajectory) -> np.ndarray:
        return self.cbt(trajectory) - 7.0 # dlmo is defines by a relationship to cbt for this model

    def amplitude(state) -> float:
        return np.sqrt(state[0]**2+state[1]**2)

    def phase(state) -> float:
        x= state[0] 
        y = state[1]*-1.0
        return np.angle(x + complex(0,1)*y)
        
    @property
    def default_initial_conditions(self) -> np.ndarray:
        """
        x= –0.3 and xc= –1.13 are the default initial conditions for the model
        should be the value near the habitual bed time of the individual. 
        """
        return np.array([-0.3,-1.13,0.0])
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def __str__(self) -> str:
        return "Forger99Model"
        

# %% ../nbs/00_models.ipynb 41
class Hannay19TP(CircadianModel):
    """  The Hannay et al 2019 two population model, which models the ventral and dorsal SCN populations """

    def __init__(self, 
                 params: dict= None # Dict of parameters to set, the published values are used by default
                 ) -> None:
        # Set the parameters to the published values by default
        self._default_params()
        if params:
            self.set_parameters(params)
        
    def _default_params(self) -> None:
        """
            Stores the default parameters for the model as published in Hannet et al 2019
        """
        
        default_params = {'tauV': 24.25,
                          'tauD': 24.0,
                          'Kvv': 0.05, 
                          'Kdd': 0.04,
                          'Kvd': 0.05,
                          'Kdv': 0.01,
                          'gamma': 0.024,
                          'A1': 0.440068, 
                          'A2': 0.159136,
                          'BetaL': 0.06452, 
                          'BetaL2': -1.38935, 
                          'sigma': 0.0477375,
                          'G': 33.75, 
                          'alpha_0': 0.05, 
                          'delta': 0.0075,
                          'p': 1.5, 
                          'I0': 9325.0}

        self.set_parameters(default_params)
        
    def set_parameters(self, 
                       param_dict: dict # Dict of parameters to set
                       ) -> None:

        params = [
            'tauV',
            'tauD',
            'Kvv',
            'Kdd',
            "Kvd",
            "Kdv",
            'gamma',
            'A1',
            'A2',
            'BetaL',
            'BetaL2',
            'sigma',
            'G',
            'alpha_0',
            'delta',
            'p',
            'I0']

        for key, value in param_dict.items():
            setattr(self, key, value)
            
    def get_parameters_array(self) -> np.ndarray: # Parameters as a numpy array
        """
            Return a numpy array of the models current parameters
        """
        return np.array([self.tauV, self.tauD, self.Kvv, self.Kdd, self.Kvd, self.Kdv, self.gamma, self.BetaL, self.BetaL2, self.A1, self.A2, self.sigma, self.G, self.alpha_0, self.delta, self.p, self.I0 ])

    @property
    def get_parameters(self) -> dict:
    
        current_params = {
            'tauV': self.w0,
            'tauD': self.tauD,
            'Kvv': self.Kvv,
            'Kdd': self.Kdd,
            'Kdv': self.Kdv,
            'Kvd': self.Kdv,
            'gamma': self.gamma,
            'A1': self.A1,
            'A2': self.A2,
            'BetaL': self.BetaL,
            'BetaL2': self.BetaL2,
            'sigma': self.sigma,
            'G': self.G,
            'alpha_0': self.alpha_0,
            'delta': self.delta,
            'p': self.p,
            'I0': self.I0}

        return (current_params)

    def alpha0(self, 
               light: float # light intensity in lux
               ) -> float: # Processed light intensity measure
        """A helper function for modeling the light input processing"""
        return (self.alpha_0 * pow(light, self.p) /
                (pow(light, self.p) + self.I0))

    def derv(self, 
             y: np.ndarray, # state vector for the dynamical system (Rv, Rd, Psiv, Psid, n)
             light: float, # light intensity in lux
             ) -> np.ndarray: # derivative of the state vector

        Rv = y[...,0]
        Rd = y[...,1]
        Psiv = y[...,2]
        Psid = y[...,3]
        n = y[...,4]

        Bhat = self.G * (1.0 - n) * self.alpha0(light=light)

        LightAmp = self.A1 * 0.5 * Bhat * (1.0 - pow(Rv, 4.0)) * np.cos(Psiv + self.BetaL) + self.A2 * 0.5 * Bhat * Rv * (
            1.0 - pow(Rv, 8.0)) * np.cos(2.0 * Psiv + self.BetaL2)
        LightPhase = self.sigma * Bhat - self.A1 * Bhat * 0.5 * (pow(Rv, 3.0) + 1.0 / Rv) * np.sin(
            Psiv + self.BetaL) - self.A2 * Bhat * 0.5 * (1.0 + pow(Rv, 8.0)) * np.sin(2.0 * Psiv + self.BetaL2)

        dydt = np.zeros_like(y)
        dydt[...,0] = -self.gamma * Rv + self.Kvv / 2.0 * Rv * (1 - pow(Rv, 4.0)) + self.Kdv / 2.0 * Rd * (
            1 - pow(Rv, 4.0)) * np.cos(Psid - Psiv) + LightAmp
        dydt[...,1] = -self.gamma * Rd + self.Kdd / 2.0 * Rd * \
            (1 - pow(Rd, 4.0)) + self.Kvd / 2.0 * Rv * (1.0 - pow(Rd, 4.0)) * np.cos(Psid - Psiv)
        dydt[...,2] = 2.0 * np.pi / self.tauV + self.Kdv / 2.0 * Rd * \
            (pow(Rv, 3.0) + 1.0 / Rv) * np.sin(Psid - Psiv) + LightPhase
        dydt[...,3] = 2.0 * np.pi / self.tauD - self.Kvd / 2.0 * \
            Rv * (pow(Rd, 3.0) + 1.0 / Rd) * np.sin(Psid - Psiv)
        dydt[...,4] = 60.0 * (self.alpha0(light=light) * (1.0 - n) - self.delta * n)
        return dydt
    
    def dlmos(self, trajectory: DynamicalTrajectory) -> np.ndarray:
        return self.observer(trajectory, Hannay19TP.DLMOObs)
    
    def cbt(self, trajectory: DynamicalTrajectory) -> np.ndarray:
        return self.observer(trajectory, Hannay19TP.CBTObs)

    def observer(self, trajectory: np.ndarray, observer_func: callable) -> np.array:
        zero_crossings = np.where(np.diff(np.sign(observer_func(0.0, trajectory.states))))[0]
        return trajectory.ts[zero_crossings]

    def DLMOObs(t, state) -> float:
        return np.sin(0.5*(Hannay19TP.phase(state)-5*np.pi/12.0))
    
    def CBTObs(t, state) -> float:
        return np.sin(0.5*(Hannay19TP.phase(state)-np.pi))

    def amplitude(state):
        # Make this joint amplitude at some point 
        return(state[0])

    def phase(state):
        return(state[2])
    
    @staticmethod
    def phase_difference(state) -> float: # Phase difference between the two oscillators
        return state[2] - state[3]
    
    @property
    def default_initial_conditions(self) -> np.ndarray:
        return np.array([1.0,1.0,0.0,0.10,0.0])
    




# %% ../nbs/00_models.ipynb 44
class Hannay19(CircadianModel):
    """
        A simple python program to integrate the human circadian rhythms model 
        (Hannay et al 2019) for a given light schedule
    """

    def __init__(self, params: dict = None):
        """
            Create a single population model by passing in a Light Function as a function of time.

            This will create a model with the default parameter values as given in Hannay et al 2019.

            This class can be used to simulate and plot the results of the given light schedule on the circadian phase
            and amplitude.
        """
        self._default_params()
        if params:
            self.set_parameters(params)

    def _default_params(self):
        """
            Use the default parameters as defined in Hannay et al 2019
        """
        default_params = {'tau': 23.84, 'K': 0.06358, 'gamma': 0.024,
                          'Beta1': -0.09318, 'A1': 0.3855, 'A2': 0.1977,
                          'BetaL1': -0.0026, 'BetaL2': -0.957756, 'sigma': 0.0400692,
                          'G': 33.75, 'alpha_0': 0.05, 'delta': 0.0075,
                          'p': 1.5, 'I0': 9325.0}

        self.set_parameters(default_params)

    def set_parameters(self, param_dict: dict):
        """
            Update the model parameters using a passed in parameter dictionary. Any parameters not included
            in the dictionary will be set to the default values.

            updateParameters(param_dict)

            Returns null, changes the parameters stored in the class instance
        """

        params = ['tau', 'K', 'gamma', 'Beta1', 'A1', 'A2', 'BetaL1',
                  'BetaL2', 'sigma', 'G', 'alpha_0', 'delta', 'p', 'I0']

        for key, value in param_dict.items():
            setattr(self, key, value)

    def get_parameters(self):
        """
            Get a dictionary of the current parameters being used by the model object.

                get_parameters()

            returns a dict of parameters
        """

        current_params = {'tau': self.tau, 'K': self.K, 'gamma': self.gamma,
                          'Beta1': self.Beta1, 'A1': self.A1, 'A2': self.A2,
                          'BetaL1': self.BetaL1,
                          'BetaL2': self.BetaL2, 'sigma': self.sigma,
                          'G': self.G, 'alpha_0': self.alpha_0,
                          'delta': self.delta, 'p': self.p, 'I0': self.I0}

        return(current_params)

    def get_parameters_array(self):
        """
            Return a numpy array of the models current parameters
        """
        return np.array([self.tau, self.K, self.gamma, self.Beta1, self.A1, self.A2, self.BetaL1, self.BetaL2, self.sigma, self.G, self.alpha_0, self.delta, self.I0, self.p])
    
    def alpha0(self, light: float):
        """A helper function for modeling the light input processing"""
        return (self.alpha_0 * pow(light, self.p) /
                (pow(light, self.p) + self.I0))
    
    def derv(self, 
             y: np.ndarray, # circadian state where the last dimension is the state variable
             light: float, # light level in lux 
             ):
        R = y[...,0]
        Psi = y[..., 1]
        n = y[...,2]

        Bhat = self.G * (1.0 - n) * self.alpha0(light=light)
        LightAmp = self.A1 * 0.5 * Bhat * (1.0 - pow(R, 4.0)) * np.cos(Psi + self.BetaL1) + self.A2 * 0.5 * Bhat * R * (
            1.0 - pow(R, 8.0)) * np.cos(2.0 * Psi + self.BetaL2)
        LightPhase = self.sigma * Bhat - self.A1 * Bhat * 0.5 * (pow(R, 3.0) + 1.0 / R) * np.sin(
            Psi + self.BetaL1) - self.A2 * Bhat * 0.5 * (1.0 + pow(R, 8.0)) * np.sin(2.0 * Psi + self.BetaL2)

        dydt = np.zeros_like(y)
        dydt[...,0] = -1.0 * self.gamma * R + self.K * \
            np.cos(self.Beta1) / 2.0 * R * (1.0 - pow(R, 4.0)) + LightAmp
        dydt[...,1] = 2*np.pi/self.tau + self.K / 2.0 * \
            np.sin(self.Beta1) * (1 + pow(R, 4.0)) + LightPhase
        dydt[...,2] = 60.0 * (self.alpha0(light=light) * (1.0 - n) - self.delta * n)

        return (dydt)
        

    def integrate_observer(self, ts: np.ndarray, light_est: np.ndarray, u0: np.ndarray = None, observer=None):
        """
            Integrate the spmodel forward in time using the given light estimate vector
        """
        if observer is None:
            observer = Hannay19.DLMOObs
        sol = self.integrate_model(ts, light_est, u0)
        zero_crossings = np.where(np.diff(np.sign(observer(0.0, sol))))[0]
        return ts[zero_crossings]
    
    def dlmos(self, trajectory: DynamicalTrajectory) -> np.ndarray:
        return self.observer(trajectory, Hannay19.DLMOObs)
    
    def cbt(self, trajectory: DynamicalTrajectory) -> np.ndarray:
        return self.observer(trajectory, Hannay19.CBTObs)

    def observer(self, trajectory: np.ndarray, observer_func: callable) -> np.array:
        zero_crossings = np.where(np.diff(np.sign(observer_func(0.0, trajectory.states)), axis=-1))[0]
        return trajectory.ts[zero_crossings]

    def DLMOObs(t, state) -> float:
        return np.sin(0.5*(Hannay19.phase(state)-5*np.pi/12.0))
    
    def CBTObs(t, state) -> float:
        return np.sin(0.5*(Hannay19.phase(state)-np.pi))

    def amplitude(state) -> float:
        return(state[0])

    def phase(state) -> float:
        return(state[1])
    
    @property
    def default_initial_conditions(self) -> np.ndarray:
        """
        Gives some default initial conditions for the model
        """
        return np.array([0.70,0.0,0.0])
    
    def guess_ic(self, time_of_day: float) -> np.ndarray:
        return np.array([0.70, phase_ic_guess(time_of_day=time_of_day), 0.0])

