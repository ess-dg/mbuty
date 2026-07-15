#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul 15 14:25:14 2026

@author: francescopiscitelli
"""

plots for SKADI 

 def plot_adc_vs_channel(self, fig_num=1006):
     """ADC vs channel 2D occupancy per hybrid, ASIC0/ASIC1 (or ch0/ch1 for clustered)."""
     if self.is_empty:
         return
     
     
     selexction is simply the ID  global 

     
     norm_colors = log_scale_norm(self.parameters.pulseHeigthSpect.plotPHSlog)

     plothtch = PlotGrid(fig_num, 1, len(self.unit_ids))
     plothtch.fig.suptitle('ADC vs CH')
     ax_e = self.axis_set.ax_energy
     m = self.matrix

     for k, uid in enumerate(self.unit_ids):
         sel = self.select_hybrid_from_unit_id(uid)

         histoch0, _, _ = self.hist.hist2d(ax_e.centers, m['adc'][sel ], self.xbins, m['channel'][sel ])
            

         plothtch.ax[0][k].imshow(histoch0, aspect='auto', norm=norm_colors, interpolation='none',
                                   extent=[ax_e.start, ax_e.stop, self.xbins[0], self.xbins[-1]], origin='lower', cmap='jet')
         

         plothtch.ax[0][k].set_xlabel('ADC')
         plothtch.ax[0][k].set_title(f'hyb.{uid}')

         if k == 0:
             plothtch.ax[0][k].set_ylabel('ASIC 0 ch no.')
             
             
             
             
             
             
          plot_phs_correlation -> NO 
          
          
          plot_multiplicity -> NO
          
          
          plot_x_lambda -> placehloder 
          plot_tof_xy    -> placehloder
          
          
          
          plot xy - plot image per bank, subplots in one fig
          
          
          
          
          