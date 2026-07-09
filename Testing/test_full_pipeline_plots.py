#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_full_pipeline_plots.py
===========================
Test file to explicitly switch on all available plotting toggles, 
calculate intermediate states, and run the pipeline from end to end.
"""

import os
import sys
import matplotlib.pyplot as plt

# =============================================================================
# RUNTIME PATH BOOTSTRAP
# =============================================================================
_workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _workspace not in sys.path:
    sys.path.insert(0, _workspace)

import newLib.libParameters as para
from mbuty_new import MBUTYOrchestrator, run_headless
from newLib.plotting_base import resolve_active_plots

def run_all_plots_pipeline():
    current_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__))) + os.sep
    params = para.parameters(current_dir)
    
    # -------------------------------------------------------------------------
    # 1. Base File Infrastructure & Acquisition Mode Set
    # -------------------------------------------------------------------------
    params.fileManagement.configFilePath = os.path.join(current_dir, 'config') + os.sep
    params.fileManagement.configFileName = "AMOR.json"
    params.acqMode = 'off'  # Open local file and visualize
    params.fileManagement.pcapLoadingMethod = 'allocate'
    
    # Enable calibrations if available
    params.dataReduction.calibrateVMM_ADC_ONOFF = True
    params.fileManagement.calibFilePath = os.path.join(current_dir, 'calib') + os.sep
    params.fileManagement.calibFileName = "AMOR_calib.json"

    # -------------------------------------------------------------------------
    # 2. FORCE EVERY SINGLE PLOT & CALCULATION TOGGLE TO TRUE
    # -------------------------------------------------------------------------
    # Core Plotting Toggles
    params.plotting.plotRawReadouts = True
    params.plotting.plotReadoutsTimeStamps = True
    params.plotting.plotADCvsCh = True
    params.plotting.plotADCvsChlog = True
    params.plotting.plotChopperResets = True
    
    params.plotting.plotRawHits = True
    params.plotting.plotHitsTimeStamps = True
    params.plotting.plotHitsTimeStampsVSChannels = True

    params.plotting.plotInstRate = True
    params.plotting.plotToFDistr = True
    params.plotting.plotMultiplicity = True 
    params.plotting.plotABSunits = True
    params.plotting.plotIMGlog = True
    params.plotting.coincidenceWS_ONOFF = True
    params.plotting.removeInvalidToFs = True
    
    # Pulse Height Spectra (PHS)
    params.pulseHeigthSpect.plotPHS = True
    params.pulseHeigthSpect.plotPHSlog = True
    params.pulseHeigthSpect.plotPHScorrelation = True
    
    # Wavelength Calculations
    params.wavelength.calculateLambda = True  
    params.wavelength.plotXLambda = True   
    params.wavelength.plotLambdaDistr = True
    
    # Beam Monitor
    params.MONitor.MONOnOff = True
    params.MONitor.plotMONtofPHS = True

    # -------------------------------------------------------------------------
    # 3. CONFIGURE MATPLOTLIB HEADLESS RUNMODE
    # -------------------------------------------------------------------------
    # We turn OFF the dashboard UI container so that all plots are built 
    # and popped instantly into plain matplotlib windows.
    params.plotting.useDashboard = True
    params.plotting.plottingInSections = False  # Keep sections off for full unified views

    # -------------------------------------------------------------------------
    # 4. RUN PIPELINE REDUCTION TRACKS
    # -------------------------------------------------------------------------
    print("\n[TEST] Bootstrapping Orchestrator and Ingesting Data Frames...")
    orchestrator = MBUTYOrchestrator(params)
    orchestrator.run_pipeline()
    
    # -------------------------------------------------------------------------
    # 5. RESOLVE AND RENDER DISCOVERED PLOTS
    # -------------------------------------------------------------------------
    print("\n[TEST] Resolving structural map of activated plot matrices...")
    detector_pipeline = orchestrator.detector_pipeline
    bm_pipeline = orchestrator.bm_pipeline
    
    dashboard_config = resolve_active_plots(
        params,
        readout_plotter=getattr(detector_pipeline, "readout_plotter", None) if detector_pipeline else None,
        hit_plotter=getattr(detector_pipeline, "hit_plotter", None) if detector_pipeline else None,
        event_plotter=getattr(detector_pipeline, "event_plotter", None) if detector_pipeline else None,
        bm_plotter=getattr(bm_pipeline, "event_plotter", None) if bm_pipeline else None,
    )

    if params.plotting.useDashboard:
        from mbuty_new import run_dashboard
        print(f"\nLaunching PySide6 Interactive Dashboard... (Embedding all toggled plots)")
        run_dashboard(orchestrator, params, dashboard_config)
    else:
        print(f"\nuseDashboard is False -- falling back to plain matplotlib windows...")
        run_headless(orchestrator, params, dashboard_config)

if __name__ == '__main__':
    run_all_plots_pipeline()