# test_Stopped_Rotor.py
# 
# Created: Feb 2020, M. Clarke
#          Sep 2020, M. Clarke 

# ----------------------------------------------------------------------
#   Imports
# ---------------------------------------------------------------------- 
import SUAVE
from SUAVE.Core import Units
from SUAVE.Plots.Mission_Plots import * 
import sys 
import numpy as np  

sys.path.append('../Vehicles')
# the analysis functions
 
from Stopped_Rotor import vehicle_setup   

# ----------------------------------------------------------------------
#   Main
# ----------------------------------------------------------------------

def main():        
        
    # ------------------------------------------------------------------------------------------------------------------
    # Stopped-Rotor   
    # ------------------------------------------------------------------------------------------------------------------
    # build the vehicle, configs, and analyses
    configs, analyses = full_setup() 
    analyses.finalize()     	   
    weights   = analyses.weights	
    breakdown = weights.evaluate()    
    mission   = analyses.mission  
    
    # evaluate mission     
    results   = mission.evaluate()
        
    # plot results
    plot_mission(results,configs)
 
    # save, load and plot old results 
    #save_stopped_rotor_results(results)
    old_results = load_stopped_rotor_results()
    plot_mission(old_results,configs, 'k-')
    
    # RPM of rotor check during hover
    RPM        = results.segments.climb_1.conditions.propulsion.rotor_rpm[0][0]
    RPM_true   = 2376.524545784301
    print(RPM) 
    diff_RPM   = np.abs(RPM - RPM_true)
    print('RPM difference')
    print(diff_RPM)
    assert np.abs((RPM - RPM_true)/RPM_true) < 1e-3  
    
    # Battery Energy Check During Transition
    battery_energy_hover_to_transition      = results.segments.transition_1.conditions.propulsion.battery_energy[:,0]
    battery_energy_hover_to_transition_true = np.array([3.21720029e+08, 3.21641741e+08, 3.21409792e+08, 3.21032453e+08,
                                                        3.20523954e+08, 3.19903500e+08, 3.19197658e+08, 3.18439186e+08,
                                                        3.17665468e+08, 3.16916703e+08, 3.16231170e+08, 3.15640856e+08,
                                                        3.15168392e+08, 3.14826640e+08, 3.14620876e+08, 3.14552284e+08])
    
    print(battery_energy_hover_to_transition)
    diff_battery_energy_hover_to_transition    = np.abs(battery_energy_hover_to_transition  - battery_energy_hover_to_transition_true) 
    print('battery_energy_hover_to_transition difference')
    print(diff_battery_energy_hover_to_transition)   
    assert all(np.abs((battery_energy_hover_to_transition - battery_energy_hover_to_transition_true)/battery_energy_hover_to_transition) < 1e-3)

    # lift Coefficient Check During Cruise
    lift_coefficient        = results.segments.cruise.conditions.aerodynamics.lift_coefficient[0][0]
    lift_coefficient_true   = 0.6953099343291548
    print(lift_coefficient)
    diff_CL                 = np.abs(lift_coefficient  - lift_coefficient_true) 
    print('CL difference')
    print(diff_CL)
    assert np.abs((lift_coefficient  - lift_coefficient_true)/lift_coefficient_true) < 1e-3    
    
    return

# ----------------------------------------------------------------------
#   Analysis Setup
# ----------------------------------------------------------------------
def full_setup():
    
    # vehicle data
    vehicle  = vehicle_setup() 

    # vehicle analyses
    analyses = base_analysis(vehicle)

    # mission analyses
    mission  = mission_setup(analyses,vehicle)

    analyses.mission = mission
    
    return  vehicle, analyses


def base_analysis(vehicle):

    # ------------------------------------------------------------------
    #   Initialize the Analyses
    # ------------------------------------------------------------------     
    analyses = SUAVE.Analyses.Vehicle()

    # ------------------------------------------------------------------
    #  Basic Geometry Relations
    sizing = SUAVE.Analyses.Sizing.Sizing()
    sizing.features.vehicle = vehicle
    analyses.append(sizing)

    # ------------------------------------------------------------------
    #  Weights
    weights = SUAVE.Analyses.Weights.Weights_Electric_Lift_Cruise()
    weights.vehicle = vehicle
    analyses.append(weights)

    # ------------------------------------------------------------------
    #  Aerodynamics Analysis
    aerodynamics = SUAVE.Analyses.Aerodynamics.Fidelity_Zero()
    aerodynamics.geometry = vehicle
    aerodynamics.settings.drag_coefficient_increment = 0.4*vehicle.excrescence_area_spin / vehicle.reference_area
    analyses.append(aerodynamics)

    # ------------------------------------------------------------------
    #  Energy
    energy= SUAVE.Analyses.Energy.Energy()
    energy.network = vehicle.propulsors 
    analyses.append(energy)

    # ------------------------------------------------------------------
    #  Planet Analysis
    planet = SUAVE.Analyses.Planets.Planet()
    analyses.append(planet)

    # ------------------------------------------------------------------
    #  Atmosphere Analysis
    atmosphere = SUAVE.Analyses.Atmospheric.US_Standard_1976()
    atmosphere.features.planet = planet.features
    analyses.append(atmosphere)   

    return analyses    


def mission_setup(analyses,vehicle):

    # ------------------------------------------------------------------
    #   Initialize the Mission
    # ------------------------------------------------------------------
    mission            = SUAVE.Analyses.Mission.Sequential_Segments()
    mission.tag        = 'the_mission'

    # airport
    airport            = SUAVE.Attributes.Airports.Airport()
    airport.altitude   =  0.0  * Units.ft
    airport.delta_isa  =  0.0
    airport.atmosphere = SUAVE.Attributes.Atmospheres.Earth.US_Standard_1976()

    mission.airport    = airport    

    # unpack Segments module
    Segments                                                 = SUAVE.Analyses.Mission.Segments
                                                             
    # base segment                                           
    base_segment                                             = Segments.Segment()
    ones_row                                                 = base_segment.state.ones_row
    base_segment.process.iterate.initials.initialize_battery = SUAVE.Methods.Missions.Segments.Common.Energy.initialize_battery
    base_segment.process.iterate.conditions.planet_position  = SUAVE.Methods.skip
    base_segment.process.iterate.unknowns.network            = vehicle.propulsors.lift_cruise.unpack_unknowns_transition
    base_segment.process.iterate.residuals.network           = vehicle.propulsors.lift_cruise.residuals_transition
    base_segment.state.unknowns.battery_voltage_under_load   = vehicle.propulsors.lift_cruise.battery.max_voltage * ones_row(1)  
    base_segment.state.residuals.network                     = 0. * ones_row(2)    


    # VSTALL Calculation
    m      = vehicle.mass_properties.max_takeoff
    g      = 9.81
    S      = vehicle.reference_area
    atmo   = SUAVE.Analyses.Atmospheric.US_Standard_1976()
    rho    = atmo.compute_values(1000.*Units.feet,0.).density
    CLmax  = 1.2 
    Vstall = float(np.sqrt(2.*m*g/(rho*S*CLmax)))

    # ------------------------------------------------------------------
    #   First Climb Segment: Constant Speed, Constant Rate
    # ------------------------------------------------------------------
    segment     = Segments.Hover.Climb(base_segment)
    segment.tag = "climb_1" 
    
    segment.analyses.extend( analyses ) 
    
    segment.altitude_start                                   = 0.0  * Units.ft
    segment.altitude_end                                     = 40.  * Units.ft
    segment.climb_rate                                       = 500. * Units['ft/min']
    segment.battery_energy                                   = vehicle.propulsors.lift_cruise.battery.max_energy
                                                             
    segment.state.unknowns.rotor_power_coefficient           = 0.02 * ones_row(1) 
    segment.state.unknowns.throttle_lift                     = 0.9  * ones_row(1) 
    segment.state.unknowns.__delitem__('throttle')

    segment.process.iterate.unknowns.network                 = vehicle.propulsors.lift_cruise.unpack_unknowns_no_forward
    segment.process.iterate.residuals.network                = vehicle.propulsors.lift_cruise.residuals_no_forward       
    segment.process.iterate.unknowns.mission                 = SUAVE.Methods.skip
    segment.process.iterate.conditions.stability             = SUAVE.Methods.skip
    segment.process.finalize.post_process.stability          = SUAVE.Methods.skip

    # add to misison
    mission.append_segment(segment)
    
    # ------------------------------------------------------------------
    #   First Cruise Segment: Transition
    # ------------------------------------------------------------------

    segment     = Segments.Transition.Constant_Acceleration_Constant_Pitchrate_Constant_Altitude(base_segment)
    segment.tag = "transition_1"

    segment.analyses.extend( analyses ) 
    segment.altitude        = 40.  * Units.ft
    segment.air_speed_start = 500. * Units['ft/min']
    segment.air_speed_end   = 0.8 * Vstall
    segment.acceleration    = 9.8/5
    segment.pitch_initial   = 0.0 * Units.degrees
    segment.pitch_final     = 5. * Units.degrees
    
    segment.state.unknowns.rotor_power_coefficient          = 0.05 *  ones_row(1)  
    segment.state.unknowns.throttle_lift                    = 0.9  * ones_row(1)  
    
    segment.state.unknowns.propeller_power_coefficient      = 0.14 *  ones_row(1) 
    segment.state.unknowns.throttle                         = 0.95  *  ones_row(1) 
    segment.state.residuals.network                         = 0.   *  ones_row(3) 

    segment.process.iterate.unknowns.network                = vehicle.propulsors.lift_cruise.unpack_unknowns_transition
    segment.process.iterate.residuals.network               = vehicle.propulsors.lift_cruise.residuals_transition    
    segment.process.iterate.unknowns.mission                = SUAVE.Methods.skip
    segment.process.iterate.conditions.stability            = SUAVE.Methods.skip
    segment.process.finalize.post_process.stability         = SUAVE.Methods.skip 
    
    # add to misison
    mission.append_segment(segment)
    
    # ------------------------------------------------------------------
    #   First Cruise Segment: Transition
    # ------------------------------------------------------------------

    segment     = Segments.Transition.Constant_Acceleration_Constant_Angle_Linear_Climb(base_segment)
    segment.tag = "transition_2"

    segment.analyses.extend( analyses ) 
    segment.altitude_start         = 40.0 * Units.ft
    segment.altitude_end           = 50.0 * Units.ft
    segment.air_speed              = 0.8 * Vstall
    segment.climb_angle            = 1 * Units.degrees
    segment.acceleration           = 0.5 * Units['m/s/s']    
    segment.pitch_initial          = 5. * Units.degrees  
    segment.pitch_final            = 7. * Units.degrees       
    
    segment.state.unknowns.rotor_power_coefficient          = 0.02  * ones_row(1)
    segment.state.unknowns.throttle_lift                    = 0.8  * ones_row(1) 
    segment.state.unknowns.propeller_power_coefficient      = 0.16  * ones_row(1)
    segment.state.unknowns.throttle                         = 0.80  * ones_row(1)   
    segment.state.residuals.network                         = 0.    * ones_row(3)    

    segment.process.iterate.unknowns.network                = vehicle.propulsors.lift_cruise.unpack_unknowns_transition
    segment.process.iterate.residuals.network               = vehicle.propulsors.lift_cruise.residuals_transition    
    segment.process.iterate.unknowns.mission                = SUAVE.Methods.skip
    segment.process.iterate.conditions.stability            = SUAVE.Methods.skip
    segment.process.finalize.post_process.stability         = SUAVE.Methods.skip

    # add to misison
    mission.append_segment(segment)
    
  
    # ------------------------------------------------------------------
    #   Second Climb Segment: Constant Speed, Constant Rate
    # ------------------------------------------------------------------

    segment     = Segments.Climb.Constant_Speed_Constant_Rate(base_segment)
    segment.tag = "climb_2"

    segment.analyses.extend( analyses )

    segment.air_speed       = 1.1*Vstall
    segment.altitude_start  = 50.0 * Units.ft
    segment.altitude_end    = 300. * Units.ft
    segment.climb_rate      = 500. * Units['ft/min']

    segment.state.unknowns.propeller_power_coefficient         = 0.16   * ones_row(1)
    segment.state.unknowns.throttle                            = 0.80   * ones_row(1)
    segment.process.iterate.unknowns.network  = vehicle.propulsors.lift_cruise.unpack_unknowns_no_lift
    segment.process.iterate.residuals.network = vehicle.propulsors.lift_cruise.residuals_no_lift     

    # add to misison
    mission.append_segment(segment)

    # ------------------------------------------------------------------
    #   Second Cruise Segment: Constant Speed, Constant Altitude
    # ------------------------------------------------------------------

    segment     = Segments.Cruise.Constant_Speed_Constant_Altitude_Loiter(base_segment)
    segment.tag = "departure_terminal_procedures"

    segment.analyses.extend( analyses )

    segment.altitude  = 300.0 * Units.ft
    segment.time      = 60.   * Units.second
    segment.air_speed = 1.2*Vstall

    segment.state.unknowns.propeller_power_coefficient =  0.16   * ones_row(1)
    segment.state.unknowns.throttle                    =  0.80   * ones_row(1)

    segment.process.iterate.unknowns.network  = vehicle.propulsors.lift_cruise.unpack_unknowns_no_lift
    segment.process.iterate.residuals.network = vehicle.propulsors.lift_cruise.residuals_no_lift     


    # add to misison
    mission.append_segment(segment)

    # ------------------------------------------------------------------
    #   Third Climb Segment: Constant Acceleration, Constant Rate
    # ------------------------------------------------------------------

    segment     = Segments.Climb.Linear_Speed_Constant_Rate(base_segment)
    segment.tag = "accelerated_climb"

    segment.analyses.extend( analyses )

    segment.altitude_start  = 300.0 * Units.ft
    segment.altitude_end    = 1000. * Units.ft
    segment.climb_rate      = 500.  * Units['ft/min']
    segment.air_speed_start = np.sqrt((500 * Units['ft/min'])**2 + (1.2*Vstall)**2)
    segment.air_speed_end   = 110.  * Units['mph']                                            

    segment.state.unknowns.propeller_power_coefficient =  0.16   * ones_row(1)
    segment.state.unknowns.throttle                    =  0.80   * ones_row(1)

    segment.process.iterate.unknowns.network  = vehicle.propulsors.lift_cruise.unpack_unknowns_no_lift
    segment.process.iterate.residuals.network = vehicle.propulsors.lift_cruise.residuals_no_lift   

    # add to misison
    mission.append_segment(segment)    

    # ------------------------------------------------------------------
    #   Third Cruise Segment: Constant Acceleration, Constant Altitude
    # ------------------------------------------------------------------

    segment     = Segments.Cruise.Constant_Speed_Constant_Altitude(base_segment)
    segment.tag = "cruise"

    segment.analyses.extend( analyses )
 
    segment.altitude  = 1000.0 * Units.ft
    segment.air_speed = 110.   * Units['mph']
    segment.distance  = 60.    * Units.miles                       

    segment.state.unknowns.propeller_power_coefficient = 0.16 * ones_row(1)  
    segment.state.unknowns.throttle                    = 0.80 * ones_row(1)

    segment.process.iterate.unknowns.network  = vehicle.propulsors.lift_cruise.unpack_unknowns_no_lift
    segment.process.iterate.residuals.network = vehicle.propulsors.lift_cruise.residuals_no_lift    


    # add to misison
    mission.append_segment(segment)     

    return mission



# ----------------------------------------------------------------------
#   Plot Results
# ----------------------------------------------------------------------
def plot_mission(results,vec_configs,line_style='bo-'):      
    
    # Plot Flight Conditions 
    plot_flight_conditions(results, line_style) 
    
    # Plot Aerodynamic Coefficients
    plot_aerodynamic_coefficients(results, line_style)  
    
    # Plot Aircraft Flight Speed
    plot_aircraft_velocities(results, line_style)
    
    # Plot Aircraft Electronics
    plot_electronic_conditions(results, line_style)
    
    # Plot Electric Motor and Propeller Efficiencies  of Lift Cruise Network
    plot_lift_cruise_network(results, line_style) 
  
    return

def load_stopped_rotor_results():
    return SUAVE.Input_Output.SUAVE.load('results_stopped_rotor.res')

def save_stopped_rotor_results(results):
    SUAVE.Input_Output.SUAVE.archive(results,'results_stopped_rotor.res')
    return
 

if __name__ == '__main__': 
    main()   
    plt.show(block=True) 
