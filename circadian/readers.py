# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/02_readers.ipynb.

# %% auto 0
__all__ = ['WearableObservation', 'AppleWatch', 'AppleWatchReader', 'Actiwatch', 'ActiwatchReader']

# %% ../nbs/02_readers.ipynb 3
from copy import deepcopy
import datetime
from datetime import datetime
import numpy as np
import pandas as pd
import pylab as plt
from dataclasses import dataclass
from scipy.stats import linregress

import json
import gzip
from typing import List
import os
from .utils import split_missing_data, split_drop_data, timezone_mapper
import random
import difflib

import os
from scipy.ndimage import gaussian_filter1d
from os import read
pd.options.mode.chained_assignment = None

import glob
import os
import random
import difflib
from scipy.ndimage import gaussian_filter1d

# %% ../nbs/02_readers.ipynb 4
@dataclass
class WearableObservation:
    steps: float
    heartrate: float
    wake: float


@dataclass
class AppleWatch:
    date_time: List[np.ndarray]
    time_total: List[np.ndarray]
    steps: List[np.ndarray]
    heartrate: List[np.ndarray] = None
    wake: List[np.ndarray] = None
    phase_measure: np.ndarray = None
    phase_measure_times: np.ndarray = None
    subject_id: str = "Anon"
    data_id: str = "None"

    def __post_init__(self):
        pass

    def build_sleep_chunks(self, chunk_jump_hrs: float = 12.0):

        time_total = np.hstack(self.time_total)
        steps = np.hstack(self.steps)
        heartrate = np.hstack(self.heartrate)
        wake = np.hstack(self.wake)

        data = np.stack((steps, heartrate, wake), axis=0)
        j_idx = np.where(np.diff(time_total) > chunk_jump_hrs)[0]
        return np.split(data, j_idx, axis=1)

    def find_disruptions(self, cutoff: float = 5.0):
        """
            Find time periods where the schedule changes by a large amount
            Should return a list of days which are signidicantly different
            then the day prior. 
        """
        idx_per_day = 240
        days_window = 3

        times_changes = []
        changes = []

        for (batch_idx, ts_batch) in enumerate(self.time_total):
            if np.sum(self.steps[batch_idx]) > 0:
                binary_steps = np.where(self.steps[batch_idx] > 1, 1.0, 0.0)
                idx_start = days_window*idx_per_day
                for day_idx in range(idx_start, len(binary_steps)-days_window*idx_per_day, 1):
                    t_before = ts_batch[day_idx -
                                        idx_per_day*days_window: day_idx]
                    t_before = t_before[binary_steps[day_idx -
                                                     idx_per_day*days_window: day_idx] < 1.0]
                    R_prior, psi_prior = times_to_angle(t_before)

                    t_after = ts_batch[day_idx:day_idx+idx_per_day*days_window]
                    t_after = t_after[binary_steps[day_idx:day_idx +
                                                   idx_per_day*days_window] < 1.0]
                    R_post, psi_post = times_to_angle(t_after)
                    psi_diff_hrs = 12.0/np.pi * \
                        np.angle(np.exp(1j*(psi_prior-psi_post)))
                    times_changes.append(ts_batch[day_idx]/24.0)
                    changes.append(psi_diff_hrs)

        return list(set([int(np.floor(x)) for (k, x) in enumerate(times_changes) if abs(changes[k]) >= cutoff]))

    def flatten(self):
        """
            Make all of the wearable time series flatten out,
            this will makes all of the time series properties
            be a list with a single element which is a numpy
            array with those values. 
        """
        self.date_time = [np.hstack(self.date_time)]
        self.time_total = [np.hstack(self.time_total)]
        self.steps = [np.hstack(self.steps)]
        self.heartrate = [np.hstack(self.heartrate)]
        if self.wake is not None:
            self.wake = [np.hstack(self.wake)]

    def get_date(self, time_hr: float):
        idx = np.argmin(np.abs(np.array(self.time_total) - time_hr))
        return pd.to_datetime(self.date_time[idx], unit='s')

    def steps_hr_loglinear(self):
        """
        Find the log steps to hr linear regression parameters .
        hr=beta*log(steps+1.0)+alpha
        Returns beta,alpha
        """
        x = np.log(np.hstack(self.steps)+1.0)
        y = np.hstack(self.heartrate)
        x = x[y > 0]
        y = y[y > 0]
        slope, intercept, r_value, p_value, std_err = linregress(x, y)
        return slope, intercept

    def get_timestamp(self, time_hr: float):
        idx = np.argmin(np.abs(np.array(np.hstack(self.time_total)) - time_hr))
        return np.hstack(self.date_time)[idx]

    def trim_data_idx(self, idx1, idx2=None):

        if idx2 is None:
            idx2 = idx1
            idx1 = 0
        self.time_total = np.hstack(self.time_total)[idx1:idx2]
        self.steps = np.hstack(self.steps)[idx1:idx2]
        if self.heartrate is not None:
            self.heartrate = np.hstack(self.heartrate)[idx1:idx2]
        self.date_time = np.hstack(self.date_time)[idx1:idx2]
        self.time_total, self.steps, self.heartrate = split_missing_data(
            self.time_total, self.steps, self.heartrate, break_threshold=96.0)

    def trim_data(self, t1: float, t2: float):
        self.flatten()

        idx_select = (self.time_total[0] >= t1) & (self.time_total[0] <= t2)
        self.time_total[0] = self.time_total[0][idx_select]
        self.steps[0] = self.steps[0][idx_select]
        self.date_time[0] = self.date_time[0][idx_select]

        if self.heartrate is not None:
            self.heartrate[0] = self.heartrate[0][idx_select]
        if self.wake is not None:
            self.wake[0] = self.wake[0][idx_select]

        self.date_time, self.time_total, self.steps, self.heartrate = split_missing_data(self.date_time[0],
                                                                                         self.time_total[0], self.steps[0], self.heartrate[0], break_threshold=96.0)

    def get_light(self, multiplier: float = 1.0):
        steps = np.hstack(self.steps)
        time_total = np.hstack(self.time_total)
        return lambda x: np.interp(x, time_total, multiplier*steps)

    def get_bounds(self):
        time_total = np.hstack(self.time_total)
        return (time_total[0], time_total[-1])

    def plot(self, t1: float = None, t2: float = None, *args, **kwargs):

        time_total = np.hstack(self.time_total)
        steps = np.hstack(self.steps)
        heartrate = np.hstack(self.heartrate)

        if self.heartrate is not None:
            hr = deepcopy(heartrate)
            hr[hr == 0] = np.nan

        time_start = t1 if t1 is not None else time_total[0]/24.0
        time_end = t2 if t2 is not None else time_total[-1]/24.0

        fig = plt.figure()
        gs = fig.add_gridspec(2, hspace=0.0)
        ax = gs.subplots(sharex=True)
        fig.suptitle(
            f"{self.data_id} Applewatch Data: Subject {self.subject_id}")
        
        if self.heartrate is not None:
            ax[0].plot(time_total / 24.0, hr, color='red', *args, **kwargs)
            
        ax[1].plot(time_total / 24.0, steps,
                   color='darkgreen', *args, **kwargs)

        if self.wake is not None:
            ax[1].plot(time_total / 24.0, np.array(self.wake) *
                       max(np.median(steps), 50.0), color='k')

        if self.phase_measure_times is not None:
            [ax[0].axvline(x=_x / 24.0, ls='--', color='blue')
             for _x in self.phase_measure_times]
            [ax[1].axvline(x=_x / 24.0, ls='--', color='blue')
             for _x in self.phase_measure_times]

        ax[1].set_xlabel("Days")
        ax[0].set_ylabel("BPM")
        ax[1].set_ylabel("Steps")
        ax[0].grid()
        ax[1].grid()
        ax[0].set_xlim((time_start, time_end))
        ax[1].set_xlim((time_start, time_end+3.0))
        ax[0].set_ylim((0, 200))
        plt.show()

    def scatter_hr_steps(self, take_log: bool = True, *args, **kwargs):
        
        if self.heartrate is None:
            print("No heartrate data")
        fig = plt.figure()
        ax = plt.gca()

        steps = np.hstack(self.steps)
        heartrate = np.hstack(self.heartrate)

        if take_log:
            ax.scatter(np.log10(steps[heartrate > 0]+1.0),
                       np.log10(heartrate[heartrate > 0]),
                       color='red',
                       *args,
                       **kwargs)
        else:
            ax.scatter(steps[heartrate > 0], heartrate[heartrate > 0],
                       color='red',
                       *args,
                       **kwargs)

        ax.set_ylabel('BPM')
        ax.set_xlabel('Steps')
        ax.set_title('Heart Rate Data')
        plt.show()

    def plot_heartrate(self, t1=None, t2=None, *args, **kwargs):

        time_total = np.hstack(self.time_total)
        steps = np.hstack(self.steps)
        heartrate = np.hstack(self.heartrate)
        time_start = t1 if t1 is not None else time_total[0]
        time_end = t2 if t2 is not None else time_total[-1]

        hr = deepcopy(heartrate)
        hr[hr == 0] = np.nan
        fig = plt.figure()
        ax = plt.gca()

        ax.plot(time_total / 24.0, hr, color='red', *args, **kwargs)
        ax.set_xlabel('Days')
        ax.set_ylabel('BPM')
        ax.set_title('Heart Rate Data')
        ax.set_ylim((0, 220))
        plt.show()

    def to_json(self):
        """
            Create a JSON version of the dataclass, can be loaded back later
        """
        for idx in range(len(self.time_total)):
            json_dict = {
                'date_time': list(self.date_time[idx]),
                'time_total': list(self.time_total[idx]),
                'steps': list(self.steps[idx]),
                'heartrate': list(self.heartrate[idx]),
                'data_id': str(self.data_id),
                'subject_id': str(self.subject_id)
            }

            if self.wake is not None:
                json_dict['wake'] = list(self.wake[idx])

            filename = 'wdap_frag_' + self.subject_id + \
                '_' + str(idx) + '.json'
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(json_dict, f, ensure_ascii=False,
                          indent=4, cls=NpEncoder)

    @classmethod
    def from_json(cls, filename):
        """
            Load data using the format specified above
        """
        jdict = json.load(open(filename, 'r'))
        cls = AppleWatch([], [], [], [])
        for s in jdict.keys():
            if isinstance(jdict[s], list):
                setattr(cls, s, [np.array(jdict[s])])
            else:
                setattr(cls, s, jdict[s])

        return cls


# %% ../nbs/02_readers.ipynb 5
class AppleWatchReader(object):

    def __init__(self, data_directory=None):
        self.data_directory = data_directory

    def utc_to_hrs(self, d: datetime):
        return d.hour+d.minute/60.0+d.second/3600.0

    def process_applewatch_pandas(self,
                                  steps: pd.DataFrame,
                                  heartrate: pd.DataFrame = None,
                                  wake: pd.DataFrame = None,
                                  bin_minutes: int = 6,
                                  debug=False,
                                  inner_join: bool = False
                                  ):

        if debug:
            mean_hr_ts = np.median(
                np.diff(np.sort(heartrate['Time'].to_numpy()))/60.0)
            print(f"The median diff in hr timestamps is: {mean_hr_ts} minutes")

        steps['Time_Start'] = pd.to_datetime(steps.Time_Start, unit='s')
        steps['Time_End'] = pd.to_datetime(steps.Time_End, unit='s')

        s1 = steps.loc[:, ['Time_Start', "Steps"]]
        s2 = steps.loc[:, ['Time_End', 'Steps']]
        s1.rename(columns={'Time_Start': 'Time'}, inplace=True)
        s2.rename(columns={'Time_End': 'Time'}, inplace=True)
        steps = pd.concat([s1, s2])
        steps.set_index('Time', inplace=True)
        steps = steps.resample(str(int(bin_minutes)) +
                               'Min').agg({'Steps': 'sum'})
        steps.reset_index(inplace=True)

        if heartrate is not None:
            if 'Time' not in heartrate:
                heartrate['Time'] = steps['Time']
                heartrate['HR'] = np.zeros(len(steps['Time']))
            heartrate['Time'] = pd.to_datetime(heartrate.Time, unit='s')
            heartrate.set_index('Time', inplace=True)
            heartrate = heartrate.resample(
                str(int(bin_minutes))+'Min').agg({'HR': 'max'})
            heartrate.reset_index(inplace=True)

            merge_method = 'inner' if inner_join else 'left'
            df = pd.merge(steps, heartrate, on='Time', how=merge_method)
            df = df.fillna(0)
        else:
            print("Skipping heartrate")

        if wake is not None:
            wake['Time'] = pd.to_datetime(wake.timestamp, unit='s')
            wake.set_index('Time', inplace=True)
            wake = wake.resample(
                str(int(bin_minutes))+'Min').agg({'wake': 'max'})
            wake.reset_index(inplace=True)
            if inner_join:
                df = pd.merge(df, wake, on='Time', how='inner')
            else:
                df = pd.merge(df, wake, on='Time', how='left')
            df.rename(columns={'wake': 'Wake'}, inplace=True)
        else:
            print("No sleep data found")

        df['UnixTime'] = (
            df['Time'] - pd.Timestamp("1970-01-01")) // pd.Timedelta('1s')

        time_start = self.utc_to_hrs(df.Time.iloc[0])
        df['TimeTotal'] = time_start + (df.UnixTime-df.UnixTime.iloc[0])/3600.0
        df['DateTime'] = pd.to_datetime(df['UnixTime'], unit='s')
        if wake is not None:
            return df[['DateTime', 'UnixTime', 'TimeTotal', 'Steps', 'HR', 'Wake']]
        else:
            return df[['DateTime', 'UnixTime', 'TimeTotal', 'Steps', 'HR']]

    
    def read_standard_csv(self,
                           directory_path: str,
                           bin_minutes: int = 6,
                           subject_id="",
                           data_id="Exporter"
                           ):

        steps = pd.read_csv(directory_path+"/combined_steps.csv")
        hr = pd.read_csv(directory_path+"/combined_heartrate.csv")

        steps.rename(columns={steps.columns[0]: 'Time_Start',
                     steps.columns[1]: 'Time_End', steps.columns[2]: 'Steps'}, inplace=True)
        hr.rename(columns={hr.columns[0]: 'Time', hr.columns[1]: 'HR'}, inplace=True)

        df = self.process_applewatch_pandas(steps, hr, bin_minutes=bin_minutes)

        aw = AppleWatch(date_time=df.UnixTime.to_numpy(),
                        time_total=df.TimeTotal.to_numpy(),
                        heartrate=df.HR.to_numpy(),
                        steps=df.Steps.to_numpy(),
                        subject_id=subject_id,
                        data_id=data_id
                        )

        return aw

    def read_standard_json(self, filepath: str,
                            bin_minutes: int = 6,
                            subject_id="",
                            data_id="Exporter",
                            sleep_trim: bool = False,
                            gzip_opt: bool = False,
                            read_sleep: bool = True
                            ):

        gzip_opt = gzip_opt if gzip_opt else filepath.endswith(".gz")
        fileobj = gzip.open(filepath, 'r') if gzip_opt else open(filepath, 'r')
        rawJson = json.load(fileobj)

        if 'wearables' in rawJson.keys():
            rawJson = rawJson['wearables']

        steps = pd.DataFrame(rawJson['steps'])
        
        if 'sleep' in rawJson.keys():
            wake = AppleWatchReader.process_sleep(rawJson) 
        else:
            wake = None 

        # Some older files use stop instead of end
        endStepPeriodName = 'end'
        if 'stop' in steps.columns:
            endStepPeriodName = 'stop'

        steps.rename(columns={'start': 'Time_Start',
                     endStepPeriodName: 'Time_End', 'steps': 'Steps'},
                     inplace=True)

        if 'heartrate' in rawJson.keys():
            hr = pd.DataFrame(rawJson['heartrate'])
            hr.rename(columns={'timestamp': 'Time',
                            'heartrate': 'HR'}, inplace=True)
        else:
            hr = None 
        df = self.process_applewatch_pandas(
            steps, hr, wake=wake, bin_minutes=bin_minutes, inner_join=True)
        
        if sleep_trim:
            df = df.dropna(subset=['Wake'])
        aw = AppleWatch(date_time=df.UnixTime.to_numpy(),
                        time_total=df.TimeTotal.to_numpy(),
                        heartrate=df.HR.to_numpy(),
                        steps=df.Steps.to_numpy(),
                        wake=df.Wake.to_numpy() if wake is not None else None,
                        subject_id=subject_id,
                        data_id=data_id
                        )

        return aw

    @staticmethod
    def process_sleep(rawJson):
        sleep_wake_upper_cutoff_hrs = 18.0
        wake_period_minimum_cutoff_seconds = 360.0
        sleep_interp_bin_secs = 60.0
        
        try:
            sleepList = [(s['interval']['start'], s['interval']['duration'], 0.0)
                        for s in rawJson['sleep'] if 'sleep' in s['value'].keys()]
        except:
            sleepList = [(s['interval']['start'], s['interval']['duration'], 0.0)
                        for s in rawJson['sleep'] if s['value'] == 'sleep']
        sleepList.sort(key=lambda x: x[0])
        for idx in range(1, len(sleepList)):
            last_sleep_end = sleepList[idx-1][0] + sleepList[idx-1][1]
            next_sleep_start = sleepList[idx][0]
            wake_duration = next_sleep_start - last_sleep_end
            if wake_duration < sleep_wake_upper_cutoff_hrs*3600.0 and wake_duration >= wake_period_minimum_cutoff_seconds:
                sleepList.append(
                    (last_sleep_end + 1.0, wake_duration - 1.0, 1.0))

        flattenSleepWakeList = []
        for s in sleepList:
            end_time = s[0] + s[1]
            last_time = s[0]

            while last_time + sleep_interp_bin_secs < end_time:
                flattenSleepWakeList.append(
                    {'timestamp': last_time, 'wake': s[2]})
                last_time += sleep_interp_bin_secs

        return pd.DataFrame(flattenSleepWakeList)
    

# %% ../nbs/02_readers.ipynb 6
@dataclass
class Actiwatch:
    date_time: np.ndarray
    time_total: np.ndarray
    lux: np.ndarray
    steps: np.ndarray
    wake: np.ndarray = None
    phase_measure: np.ndarray = None
    phase_measure_times: np.ndarray = None
    subject_id: str = "Anon"
    data_id: str = "None"

    def get_light(self, multiplier: float = 1.0):
        self.lux = np.absolute(np.array(self.lux))
        return lambda x: np.interp(x, self.time_total, multiplier*self.lux, left=0.0, right=0.0)

    def get_activity_light(self, multiplier: float = 1.0):
        self.steps = np.array(self.steps)
        return lambda x: np.interp(x, self.time_total, multiplier*self.steps, left=0.0, right=0.0)

    def to_dataframe(self):
        """
            Get a pandas dataframe verison of the actiwatch data 
        """
        df = pd.DataFrame({'date_time': self.date_time,
                           'time_total': self.time_total,
                          'lux': self.lux,
                           'steps': self.steps,
                           'wake': self.wake
                           })
        return df

    def get_bounds(self):
        return (self.time_total[0], self.time_total[-1])

    def plot(self, show=True, vlines=None, *args, **kwargs):

        fig = plt.figure()
        gs = fig.add_gridspec(2, hspace=0)
        ax = gs.subplots(sharex=True)
        fig.suptitle(
            f"{self.data_id} Actiwatch Data: Subject {self.subject_id}")
        ax[0].plot(self.time_total / 24.0, np.log10(self.lux+1), color='red')
        ax[1].plot(self.time_total / 24.0, self.steps, color='darkgreen')
        print(np.median(self.steps))
        print(self.wake)
        try:
            ax[1].plot(self.time_total / 24.0, self.wake *
                       np.median(self.steps), color='k')
        except:
            print(f"Error with wake plot with {self.subject_id}")

        if self.phase_measure_times is not None:
            [ax[0].axvline(x=_x / 24.0, ls='--', color='blue')
             for _x in self.phase_measure_times]
            [ax[1].axvline(x=_x / 24.0, ls='--', color='blue')
             for _x in self.phase_measure_times]

        if vlines is not None:
            [ax[0].axvline(x=_x / 24.0, ls='--', color='cyan')
             for _x in vlines]
            [ax[1].axvline(x=_x / 24.0, ls='--', color='cyan')
             for _x in vlines]

        ax[1].set_xlabel("Days")
        ax[0].set_ylabel("Lux (log 10)")
        ax[1].set_ylabel("Activity Counts")
        ax[0].grid()
        ax[1].grid()
        if show:
            plt.show()
        else:
            return ax


# %% ../nbs/02_readers.ipynb 7
class ActiwatchReader(object):

    def __init__(self, data_directory=None):
        self.data_directory = data_directory

    def utc_to_hrs(self, d: datetime):
        return d.hour+d.minute/60.0+d.second/3600.0

    def process_actiwatch(self, 
                          df: pd.DataFrame,
                          MIN_LIGHT_THRESHOLD=5000,
                          round_data=True,
                          bin_minutes=6,
                          dt_format: str = "%m/%d/%Y %I:%M:%S %p"):
        """
            Takes in a dataframe with columns 
                Date : str 
                Time : str 
                White Light: float 
                Sleep/Wake: float 
                Activity: float
            returns a cleaned dataframe with columns
                "DateTime", "TimeTotal", "UnixTime", "Activity", "Lux", "Wake"
        """
        df['DateTime'] = df['Date']+" "+df['Time']
        df['DateTime'] = pd.to_datetime(
            df.DateTime, format=dt_format)

        df['UnixTime'] = (
            df['DateTime'] - pd.Timestamp("1970-01-01")) // pd.Timedelta('1s')
        df['Lux'] = df['White Light']
        df.rename(columns={'Sleep/Wake': 'Wake'}, inplace=True)

        df['Lux'].fillna(0, inplace=True)
        df['LightSum'] = np.cumsum(df.Lux.values)
        df['LightSumReverse'] = np.sum(
            df.Lux.values) - np.cumsum(df.Lux.values) + 1.0

        df = df[(df.LightSum > MIN_LIGHT_THRESHOLD) & (
            df.LightSumReverse > MIN_LIGHT_THRESHOLD)]

        time_start = self.utc_to_hrs(df.DateTime.iloc[0])
        df2 = df[['UnixTime']].copy(deep=True)
        base_unix_time = df2['UnixTime'].iloc[0]
        df['TimeTotal'] = time_start + \
            (df2.loc[:, ['UnixTime']]-base_unix_time)/3600.0

        df = df[["DateTime", "TimeTotal", "UnixTime", "Activity", "Lux", "Wake"]]
        if round_data:
            df.set_index('DateTime', inplace=True)
            df = df.resample(str(int(bin_minutes))+'Min').agg({'TimeTotal': 'min',
                                                              'UnixTime': 'min',
                                                               'Activity': 'sum',
                                                               'Lux': 'median',
                                                               'Wake': 'max'})
            df.reset_index(inplace=True)

        # Not sure why hchs needs this
        df['TimeTotal'].interpolate(inplace=True)
        df.fillna(0, inplace=True)
        return df
    
