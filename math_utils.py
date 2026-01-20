"""
@author: Julian Cabaleiro
@repository: https://github.com/juliancabaleiro/H5Inspector

Mathematical and Signal Processing Functions
"""
import numpy as np
import logging

def calculate_statistics(y_data: np.ndarray):
    """
    Calculate basic statistics for a given array.
    
    Parameters
    ----------
    y_data : np.ndarray
        Input data array.
        
    Returns
    -------
    dict
        Dictionary containing calculated statistics (Average, Max, Min,
        Pk-Pk, Std Dev, RMS) or empty if calculation fails.
    """
    if len(y_data) == 0:
        return {}
        
    stats = {}
    try:
        # Convert to float and handle finite values for core stats
        y_float = y_data.astype(float)
        
        # Use nan-safe versions for robustness
        stats['Average'] = np.nanmean(y_float)
        stats['Max'] = np.nanmax(y_float)
        stats['Min'] = np.nanmin(y_float)
        stats['Pk-Pk'] = stats['Max'] - stats['Min']
        stats['Std Dev'] = np.nanstd(y_float)
        
        # RMS calculation
        y_finite = y_float[np.isfinite(y_float)]
        if len(y_finite) > 0:
            with np.errstate(invalid='ignore', over='ignore'):
                mean_sq = np.mean(y_finite**2)
                if mean_sq >= 0 and np.isfinite(mean_sq):
                    stats['RMS'] = np.sqrt(mean_sq)
                else:
                    stats['RMS'] = np.nan
        else:
            stats['RMS'] = np.nan
    except Exception as e:
        # Fallback if conversion or calculation fails
        logging.error(f"Error calculating statistics: {e}")
        return {}
        
    return stats

def get_window(name: str, n: int):
    """
    Return a window function by name.
    
    Parameters
    ----------
    name : str
        Name of the window function (Hann, Hamming, Blackman, Gabor, Rectangular).
    n : int
        Number of points in the window.
        
    Returns
    -------
    np.ndarray
        Window array of length n.
    """
    if name == "Hann":
        return np.hanning(n)
    elif name == "Hamming":
        return np.hamming(n)
    elif name == "Blackman":
        return np.blackman(n)
    elif name == "Gabor":
        # Gaussian window (Gabor-like)
        # std = n/8 is a common choice for Gaussian windows in STFT/FFT
        return np.exp(-0.5 * (np.arange(n) - (n-1)/2)**2 / ((n/8)**2))
    else: # Rectangular
        return np.ones(n)

def calculate_fft(signal: np.ndarray, fs: float = 1.0, window_name: str = "Rectangular"):
    """
    Calculate FFT of a signal with windowing and frequency scaling.
    
    Parameters
    ----------
    signal : np.ndarray
        Input time-domain signal.
    fs : float, optional
        Sampling frequency in Hz, by default 1.0.
    window_name : str, optional
        Name of the window function to apply, by default "Rectangular".
        
    Returns
    -------
    tuple or None
        Tuple (freqs, magnitude, phase, mag_db, thd) or None if input invalid.
    """
    n = len(signal)
    if n < 2:
        return None
        
    # Remove DC component to avoid leakage from 0Hz
    signal_ac = signal - np.nanmean(signal)
    
    # Apply window
    win = get_window(window_name, n)
    win_sum = np.sum(win)
    if win_sum == 0: win_sum = 1.0
    
    windowed_signal = signal_ac * win
    
    # RFFT for real signals
    fft_vals = np.fft.rfft(windowed_signal)
    freqs = np.fft.rfftfreq(n, d=1.0/fs)
    
    # Magnitude (corrected for window and RFFT symmetry)
    magnitude = 2.0 * np.abs(fft_vals) / win_sum
    
    # Phase
    phase = np.angle(fft_vals)
    
    # dB Magnitude
    mag_db = 20 * np.log10(np.clip(magnitude, 1e-12, None))
    
    # Calculate THD (%)
    thd = calculate_thd(magnitude, freqs)
    
    return freqs, magnitude, phase, mag_db, thd

def calculate_thd(magnitude: np.ndarray,
                  freqs: np.ndarray,
                  max_harmonic: int = 40,
                  bins_per_harmonic: int = 1,
                  fundamental_freq: float = None) -> float:
    """
    Calculate Total Harmonic Distortion (THD) in %.
    
    Parameters
    ----------
    magnitude : np.ndarray
        Magnitude spectrum of the signal.
    freqs : np.ndarray
        Frequency vector corresponding to the magnitude spectrum.
    max_harmonic : int, optional
        Maximum harmonic to include in calculation, by default 40.
    bins_per_harmonic : int, optional
        Number of bins to sum around each harmonic to account for leakage, by default 1.
    fundamental_freq : float, optional
        Fundamental frequency to use. If None, it is auto-detected as the max peak.
        
    Returns
    -------
    float
        THD value in percentage.
    """

    # Evitar DC
    dc_skip = 1
    
    if fundamental_freq is not None:
        # Find index for provided fundamental
        fund_idx = np.argmin(np.abs(freqs - fundamental_freq))
    else:
        # Auto-detect
        fund_idx = np.argmax(magnitude[dc_skip:]) + dc_skip
        
    fund_mag = magnitude[fund_idx]
    f0 = freqs[fund_idx]

    if fund_mag < 1e-12 or f0 <= 0:
        return 0.0

    harmonic_power = 0.0

    for k in range(2, max_harmonic + 1):
        fk = k * f0
        if fk > freqs[-1]:
            break

        idx = np.argmin(np.abs(freqs - fk))

        # Sumar potencia alrededor del armónico (leakage)
        i0 = max(idx - bins_per_harmonic, 0)
        i1 = min(idx + bins_per_harmonic + 1, len(magnitude))

        harmonic_power += np.sum(magnitude[i0:i1] ** 2)

    thd = np.sqrt(harmonic_power) / fund_mag
    return thd * 100


def find_peak(freqs: np.ndarray, magnitude: np.ndarray):
    """
    Find peak frequency and magnitude.
    
    Parameters
    ----------
    freqs : np.ndarray
        Frequency vector.
    magnitude : np.ndarray
        Magnitude vector.
        
    Returns
    -------
    tuple
        (peak_frequency, peak_magnitude).
    """
    if len(magnitude) == 0:
        return 0.0, 0.0
    idx = np.argmax(magnitude)
    return freqs[idx], magnitude[idx]
