# -*- coding: utf-8 -*-
"""
Created on Thu Jun 30 10:34:37 2016

@author: slauniai

"""
import numpy as np
import pandas as pd
import os
import configparser
import matplotlib.pyplot as plt
import seaborn as sns
# from scipy import interpolate

eps = np.finfo(float).eps  # machine epsilon

#""" ****** set here spathy data path *** """
# data_path = os.path.join('c:/', 'Datat/SpathyData/SVECatchments')
# spathy_path = os.path.join('c:/', 'Repositories/spathy')
# os.chdir(spathy_path)


def clear_console():
    """
    clears Spyder console window - does not affect namespace
    """
    import os
    clear = lambda: os.system('cls')
    clear()
    return None

""" Functions for data input and output """



"""
***** SVE -valuma-alueet -- get gis data to create catchment ******
"""
def create_catchment(pgen, fpath, plotgrids=False, plotdistr=False):
    """
    reads gis-data grids from selected catchments and returns numpy 2d-arrays
    IN:
        ID - SVE catchment ID (int or str)
        fpath - folder (str)
        psoil - soil properties
        plotgrids - True plots
    OUT:
        GisData - dictionary with 2d numpy arrays and some vectors/scalars.

        keys [units]:'dem'[m],'slope'[deg],'soil'[coding 1-4], 'cf'[-],'flowacc'[m2], 'twi'[log m??],
        'vol'[m3/ha],'ba'[m2/ha], 'age'[yrs], 'hc'[m], 'bmroot'[1000kg/ha],'LAI_pine'[m2/m2 one-sided],'LAI_spruce','LAI_decid',
        'info','lat0'[latitude, euref_fin],'lon0'[longitude, euref_fin],loc[outlet coords,euref_fin],'cellsize'[cellwidth,m],
        'peatm','stream','cmask','rockm'[masks, 1=True]      
        
    TODO (6.2.2017 Samuli): 
        mVMI-datan koodit >32766 ovat vesialueita ja ei-metsäalueita (tiet, sähkölinjat, puuttomat suot) käytä muita maskeja (maastotietokanta, kysy
        Auralta tie + sähkölinjamaskit) ja IMPOSE LAI ja muut muuttujat ko. alueille. Nyt menevät no-data -luokkaan eikä oteta mukaan laskentaan.
    """
    ID=pgen['catchment_id']
    # fpath = os.path.join(fpath, str(ID) + '\\sve_' + str(ID) + '_')
    #fpath = os.path.join(fpath, str(ID))
    bname = 'sve_' + str(ID) + '_'
    #bname = pgen['prefix'] + '_'+ str(ID) + '_' 
    #bname = ' '    
    #print os.path.join(fpath, bname + 'dem_16m_aggr.asc')            
    # specific leaf area (m2/kg) for converting leaf mass to leaf area        
    # SLA = {'pine': 5.54, 'spruce': 5.65, 'decid': 18.46}  # m2/kg, Kellomäki et al. 2001 Atm. Env.
    SLA = {'pine': 6.8, 'spruce': 4.7, 'decid': 14.0}  # Härkönen et al. 2015 BER 20, 181-195
    
    # values to be set for 'open peatlands' and 'not forest land'
    nofor = {'vol': 0.1, 'ba': 0.01, 'height': 0.1, 'cf': 0.01, 'age': 0.0, 
             'LAIpine': 0.01, 'LAIspruce': 0.01, 'LAIdecid': 0.01, 'bmroot': 0.01}
    opeatl = {'vol': 0.01, 'ba': 0.01, 'height': 0.1, 'cf': 0.1, 'age': 0.0,
              'LAIpine': 0.01, 'LAIspruce': 0.01, 'LAIdecid': 0.1, 'bmroot': 0.01}

    # dem, set values outside boundaries to NaN
    dem, info, pos, cellsize, nodata = read_AsciiGrid(os.path.join(fpath, bname + 'dem_16m_aggr.asc'))
    # latitude, longitude arrays    
    nrows, ncols = np.shape(dem)
    lon0 = np.arange(pos[0], pos[0] + cellsize*ncols, cellsize)
    lat0 = np.arange(pos[1], pos[1] + cellsize*nrows, cellsize)
    lat0 = np.flipud(lat0)  # why this is needed to get coordinates correct when plotting?
    # catchment mask cmask ==1, np.nan outside
    cmask = dem.copy()
    cmask[np.isfinite(cmask)] = 1.0
    # flowacc, D-infinity, nr of draining cells
    flowacc, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'flow_accum_D-inf_grids.asc'))
    flowacc = flowacc*cellsize**2  # in m2
    # slope, degrees
    slope, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'slope_16m.asc'))
    # twi
    twi, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'TWI_16m.asc'))
    """
    Create soiltype grid and masks for waterbodies, streams, peatlands and rocks
    """
    # Maastotietokanta water bodies: 1=waterbody
    stream, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'vesielementit_mtk.asc'))
    stream[np.isfinite(stream)] = 1.0
    # maastotietokanta peatlandmask
    peatm, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'suo_mtk.asc'))
    peatm[np.isfinite(peatm)] = 1.0
    # maastotietokanta kalliomaski
    rockm, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'kallioalue_mtk.asc'))
    rockm[np.isfinite(rockm)] = 1.0
    """
    gtk soilmap: read and re-classify into 4 texture classes
    #GTK-pintamaalaji grouped to 4 classes (Samuli Launiainen, Jan 7, 2017)
    #Codes based on maalaji 1:20 000 AND ADD HERE ALSO 1:200 000
    """
    CoarseTextured = [195213, 195314, 19531421, 195313, 195310]
    MediumTextured = [195315, 19531521, 195215, 195214, 195601, 195411, 195112,
                      195311, 195113, 195111, 195210, 195110, 195312]
    FineTextured = [19531521, 195412, 19541221, 195511, 195413, 195410,
                    19541321, 195618]
    Peats = [195512, 195513, 195514, 19551822, 19551891, 19551892]
    Water = [195603]

    gtk_s, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'soil.asc')) 
    #gtk_s, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'soil_pintamaa.asc')) 

 
    r, c = np.shape(gtk_s)
    soil = np.ravel(gtk_s)
    #del gtk_s

    soil[np.in1d(soil, CoarseTextured)] = 1.0  # ; soil[f]=1; del f
    soil[np.in1d(soil, MediumTextured)] = 2.0
    soil[np.in1d(soil, FineTextured)] = 3.0
    soil[np.in1d(soil, Peats)] = 4.0
    soil[np.in1d(soil, Water)] = -1.0

    # reshape back to original grid
    soil = soil.reshape(r, c)
    del r, c
    soil[np.isfinite(peatm)] = 4.0
    
    # update waterbody mask
    ix = np.where(soil == -1.0)
    stream[ix] = 1.0
    
    # update catchment mask so that water bodies are left out (SL 20.2.18)
    #cmask[soil == -1.0] = np.nan
    
    #Warn, remove this
    cmask[soil <= 0] = np.nan

    soil = soil * cmask
    
    """ stand data (MNFI)"""
    # stand volume [m3ha-1]
    vol, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'tilavuus.asc'), setnans=False)
    vol = vol*cmask

    # indexes for cells not recognized in mNFI
    ix_n = np.where((vol >= 32727) | (vol == -9999) )  # no satellite cover or not forest land: assign arbitrary values 
    ix_p = np.where((vol >= 32727) & (peatm == 1))  # open peatlands: assign arbitrary values
    ix_w = np.where((vol >= 32727) & (stream == 1))  # waterbodies: leave out
    cmask[ix_w] = np.nan  # NOTE: leaves waterbodies out of catchment mask
    vol[ix_n] = nofor['vol']
    vol[ix_p] = opeatl['vol']
    vol[ix_w] = np.nan

    #pine volume [m3 ha-1]
    p_vol, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname +'manty.asc'))
    p_vol = p_vol*cmask
    #spruce volume [m3 ha-1]
    s_vol, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname +'kuusi.asc'))
    s_vol = s_vol*cmask
    #birch volume [m3 ha-1]
    b_vol, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname +'koivu.asc'))
    b_vol = b_vol*cmask
    

    # basal area [m2 ha-1]
    ba, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'ppa.asc') )
    ba[ix_n] = nofor['ba']
    ba[ix_p] = opeatl['ba']
    ba[ix_w] = np.nan

    # tree height [m]
    height, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'keskipituus.asc'))
    height = 0.1*height  # m
    height[ix_n] = nofor['height']
    height[ix_p] = opeatl['height']
    height[ix_w] = np.nan

    # canopy closure [-]    
    cf, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'latvuspeitto.asc'))
    cf = 1e-2*cf
    cf[ix_n] = nofor['cf']
    cf[ix_p] = opeatl['cf']
    cf[ix_w] = np.nan
    # cfd, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'lehtip_latvuspeitto.asc'))
    # cfd = 1e-2*cfd  # percent to fraction

    # stand age [yrs]
    age, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname+'ika.asc'))
    age[ix_n] = nofor['age']
    age[ix_p] = opeatl['age']
    age[ix_w] = np.nan

    # leaf biomasses and one-sided LAI
    bmleaf_pine, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'bm_manty_neulaset.asc'))
    bmleaf_spruce, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'bm_kuusi_neulaset.asc'))
    bmleaf_decid, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'bm_lehtip_neulaset.asc'))
    # bmleaf_pine[ix_n]=np.nan; bmleaf_spruce[ix_n]=np.nan; bmleaf_decid[ix_n]=np.nan;

    LAI_pine = 1e-3*bmleaf_pine*SLA['pine']  # 1e-3 converts 10kg/ha to kg/m2
    LAI_pine[ix_n] = nofor['LAIpine']
    LAI_pine[ix_p] = opeatl['LAIpine']
    LAI_pine[ix_w] = np.nan

    LAI_spruce = 1e-3*bmleaf_spruce*SLA['spruce']
    LAI_spruce[ix_n] = nofor['LAIspruce']
    LAI_spruce[ix_p] = opeatl['LAIspruce']
    LAI_spruce[ix_w] = np.nan

    LAI_decid = 1e-3*bmleaf_decid*SLA['decid']
    LAI_decid[ix_n] = nofor['LAIdecid']
    LAI_decid[ix_p] = opeatl['LAIdecid']
    LAI_decid[ix_w] = np.nan

    bmroot_pine, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'bm_manty_juuret.asc'))
    bmroot_spruce, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'bm_kuusi_juuret.asc'))
    bmroot_decid, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'bm_lehtip_juuret.asc'))  
    bmroot = 1e-2*(bmroot_pine + bmroot_spruce + bmroot_decid)  # 1000 kg/ha
    bmroot[ix_n] = nofor['bmroot']
    bmroot[ix_p] = opeatl['bmroot']
    bmroot[ix_w] = np.nan
    # site types
    maintype, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'paatyyppi.asc'))
    maintype = maintype*cmask
    sitetype, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'kasvupaikka.asc'))
    sitetype = sitetype*cmask
    #HERE DUPLICATE, REMOVE LATER    
    #site main class: 1- mineral soil; 2-spruce fen; 3-pine bog; 4-open peatland
    smc, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname +'paatyyppi.asc'))
    smc = smc*cmask
    #site fertility class: 1- ... 8 (1 Lehdot, 2 OMT, 3 MT, 4...)
    sfc, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname +'kasvupaikka.asc'))
    sfc = sfc*cmask
    # downslope distance
    print ('Warning: dsdistance decativated!')
    #dsdist, _, _, _, _  = read_AsciiGrid(os.path.join(fpath, bname +'downslope_distance.asc'))
    dsdist=None
    
    
    
    # catchment outlet location and catchment mean elevation
    (iy, ix) = np.where(flowacc == np.nanmax(flowacc))
    loc = {'lat': lat0[iy], 'lon': lon0[ix], 'elev': np.nanmean(dem)}
    # dict of all rasters
    GisData = {'cmask': cmask, 'dem': dem, 'flowacc': flowacc, 'slope': slope,
               'twi': twi, 'gtk_soilcode': gtk_s, 'soilclass': soil, 'peatm': peatm, 'stream': stream,
               'rockm': rockm, 'LAI_pine': LAI_pine, 'LAI_spruce': LAI_spruce,
               'LAI_conif': LAI_pine + LAI_spruce, 'smc':smc, 'sfc': sfc, 'soil':soil,
               'LAI_decid': LAI_decid, 'bmroot': bmroot, 'ba': ba, 'hc': height,
               'vol': vol, 'p_vol':p_vol,'s_vol':s_vol,'b_vol':b_vol,'cf': cf, 'age': age, 'maintype': maintype, 'sitetype': sitetype,
               'cellsize': cellsize, 'info': info, 'lat0': lat0, 'lon0': lon0, 'loc': loc, 'dsdist':dsdist}   

    if plotgrids is True:
        # %matplotlib qt
        # xx, yy = np.meshgrid(lon0, lat0)
        plt.close('all')

        plt.figure()

        plt.subplot(221)
        plt.imshow(dem); plt.colorbar(); plt.title('DEM (m)')
        plt.plot(ix, iy,'rs')
        plt.subplot(222)
        plt.imshow(twi); plt.colorbar(); plt.title('TWI')
        plt.subplot(223)
        plt.imshow(slope); plt.colorbar(); plt.title('slope(deg)')
        plt.subplot(224)
        plt.imshow(flowacc); plt.colorbar(); plt.title('flowacc (m2)')

        plt.figure(figsize=(6, 14))

        plt.subplot(221)
        plt.imshow(soil); plt.colorbar(); plt.title('soiltype')
        mask = cmask.copy()*0.0
        mask[np.isfinite(peatm)] = 1
        mask[np.isfinite(rockm)] = 2
        mask[np.isfinite(stream)] = 3

        plt.subplot(222)
        plt.imshow(mask); plt.colorbar(); plt.title('masks')
        plt.subplot(223)
        plt.imshow(LAI_pine+LAI_spruce + LAI_decid); plt.colorbar(); plt.title('LAI (m2/m2)')
        plt.subplot(224)
        plt.imshow(cf); plt.colorbar(); plt.title('cf (-)')

        
        plt.figure(figsize=(6,11))
        plt.subplot(321)
        plt.imshow(vol); plt.colorbar(); plt.title('vol (m3/ha)')
        plt.subplot(323)
        plt.imshow(height); plt.colorbar(); plt.title('hc (m)')
        #plt.subplot(223)
        #plt.imshow(ba); plt.colorbar(); plt.title('ba (m2/ha)')
        plt.subplot(325)
        plt.imshow(age); plt.colorbar(); plt.title('age (yr)')
        plt.subplot(322)
        plt.imshow(1e-3*bmleaf_pine); plt.colorbar(); plt.title('pine needles (kg/m2)')
        plt.subplot(324)
        plt.imshow(1e-3*bmleaf_spruce); plt.colorbar(); plt.title('spruce needles (kg/m2)')
        plt.subplot(326)
        plt.imshow(1e-3*bmleaf_decid); plt.colorbar(); plt.title('decid. leaves (kg/m2)')

    if plotdistr is True:
        twi0 = twi[np.isfinite(twi)]
        vol = vol[np.isfinite(vol)]
        lai = LAI_pine + LAI_spruce + LAI_decid
        lai = lai[np.isfinite(lai)]
        soil0 = soil[np.isfinite(soil)]
        
        plt.figure(100)
        plt.subplot(221)
        plt.hist(twi0, bins=100, color='b', alpha=0.5, normed=True)
        plt.ylabel('f');plt.ylabel('twi')

        s = np.unique(soil0)
        colcode = 'rgcym'
        for k in range(0,len(s)):
            # print k
            a = twi[np.where(soil==s[k])]
            a = a[np.isfinite(a)]
            plt.hist(a, bins=50, alpha=0.5, color=colcode[k], normed=True, label='soil ' +str(s[k]))
        plt.legend()
        plt.show()

        plt.subplot(222)
        plt.hist(vol, bins=100, color='k', normed=True); plt.ylabel('f'); plt.ylabel('vol')
        plt.subplot(223)
        plt.hist(lai, bins=100, color='g', normed=True); plt.ylabel('f'); plt.ylabel('lai')
        plt.subplot(224)
        plt.hist(soil0, bins=5, color='r', normed=True); plt.ylabel('f');plt.ylabel('soiltype')

    return GisData

def create_catchment_bck(pgen, fpath, plotgrids=False, plotdistr=False):
    """
    reads gis-data grids from selected catchments and returns numpy 2d-arrays
    IN:
        ID - SVE catchment ID (int or str)
        fpath - folder (str)
        psoil - soil properties
        plotgrids - True plots
    OUT:
        GisData - dictionary with 2d numpy arrays and some vectors/scalars.

        keys [units]:'dem'[m],'slope'[deg],'soil'[coding 1-4], 'cf'[-],'flowacc'[m2], 'twi'[log m??],
        'vol'[m3/ha],'ba'[m2/ha], 'age'[yrs], 'hc'[m], 'bmroot'[1000kg/ha],'LAI_pine'[m2/m2 one-sided],'LAI_spruce','LAI_decid',
        'info','lat0'[latitude, euref_fin],'lon0'[longitude, euref_fin],loc[outlet coords,euref_fin],'cellsize'[cellwidth,m],
        'peatm','stream','cmask','rockm'[masks, 1=True]      
        
    TODO (6.2.2017 Samuli): 
        mVMI-datan koodit >32766 ovat vesialueita ja ei-metsäalueita (tiet, sähkölinjat, puuttomat suot) käytä muita maskeja (maastotietokanta, kysy
        Auralta tie + sähkölinjamaskit) ja IMPOSE LAI ja muut muuttujat ko. alueille. Nyt menevät no-data -luokkaan eikä oteta mukaan laskentaan.
    """
    ID=pgen['catchment_id']
    # fpath = os.path.join(fpath, str(ID) + '\\sve_' + str(ID) + '_')
    #fpath = os.path.join(fpath, str(ID))
    #bname = 'sve_' + str(ID) + '_'
    bname = pgen['prefix'] + '_'+ str(ID) + '_' 
    #bname = ''    
    print(fpath)            
    # specific leaf area (m2/kg) for converting leaf mass to leaf area        
    # SLA = {'pine': 5.54, 'spruce': 5.65, 'decid': 18.46}  # m2/kg, Kellomäki et al. 2001 Atm. Env.
    SLA = {'pine': 6.8, 'spruce': 4.7, 'decid': 14.0}  # Härkönen et al. 2015 BER 20, 181-195
    
    # values to be set for 'open peatlands' and 'not forest land'
    nofor = {'vol': 0.1, 'ba': 0.01, 'height': 0.1, 'cf': 0.01, 'age': 0.0, 
             'LAIpine': 0.01, 'LAIspruce': 0.01, 'LAIdecid': 0.01, 'bmroot': 0.01}
    opeatl = {'vol': 0.01, 'ba': 0.01, 'height': 0.1, 'cf': 0.1, 'age': 0.0,
              'LAIpine': 0.01, 'LAIspruce': 0.01, 'LAIdecid': 0.1, 'bmroot': 0.01}

    # dem, set values outside boundaries to NaN
    dem, info, pos, cellsize, nodata = read_AsciiGrid(os.path.join(fpath, bname + 'dem_16m.asc'))
    # latitude, longitude arrays    
    nrows, ncols = np.shape(dem)
    lon0 = np.arange(pos[0], pos[0] + cellsize*ncols, cellsize)
    lat0 = np.arange(pos[1], pos[1] + cellsize*nrows, cellsize)
    lat0 = np.flipud(lat0)  # why this is needed to get coordinates correct when plotting?
    # catchment mask cmask ==1, np.nan outside
    cmask = dem.copy()
    cmask[np.isfinite(cmask)] = 1.0
    # flowacc, D-infinity, nr of draining cells
    flowacc, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'flowaccum_16m.asc'))
    flowacc = flowacc*cellsize**2  # in m2
    # slope, degrees
    slope, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'slope_16m.asc'))
    # twi
    twi, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'twi_16m.asc'))
    """
    Create soiltype grid and masks for waterbodies, streams, peatlands and rocks
    """
    # Maastotietokanta water bodies: 1=waterbody
    stream, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'vesielementit.asc'))
    stream[np.isfinite(stream)] = 1.0
    # maastotietokanta peatlandmask
    peatm, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'suo_16m.asc'))
    peatm[np.isfinite(peatm)] = 1.0
    # maastotietokanta kalliomaski
    rockm, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'kallioalue_16m.asc'))
    rockm[np.isfinite(rockm)] = 1.0
    """
    gtk soilmap: read and re-classify into 4 texture classes
    #GTK-pintamaalaji grouped to 4 classes (Samuli Launiainen, Jan 7, 2017)
    #Codes based on maalaji 1:20 000 AND ADD HERE ALSO 1:200 000
    """
    CoarseTextured = [195213, 195314, 19531421, 195313, 195310]
    MediumTextured = [195315, 19531521, 195215, 195214, 195601, 195411, 195112,
                      195311, 195113, 195111, 195210, 195110, 195312]
    FineTextured = [19531521, 195412, 19541221, 195511, 195413, 195410,
                    19541321, 195618]
    Peats = [195512, 195513, 195514, 19551822, 19551891, 19551892]
    Water = [195603]

    gtk_s, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'soil_merged_pintamaa_cl.asc')) 
 
    r, c = np.shape(gtk_s)
    soil = np.ravel(gtk_s)
    #del gtk_s

    soil[np.in1d(soil, CoarseTextured)] = 1.0  # ; soil[f]=1; del f
    soil[np.in1d(soil, MediumTextured)] = 2.0
    soil[np.in1d(soil, FineTextured)] = 3.0
    soil[np.in1d(soil, Peats)] = 4.0
    soil[np.in1d(soil, Water)] = -1.0

    # reshape back to original grid
    soil = soil.reshape(r, c)
    del r, c
    soil[np.isfinite(peatm)] = 4.0
    # update waterbody mask
    ix = np.where(soil == -1.0)
    stream[ix] = 1.0
    
    # update catchment mask so that water bodies are left out (SL 20.2.18)
    #cmask[soil == -1.0] = np.nan
    cmask[soil <= 0] = np.nan

    soil = soil * cmask
    
    """ stand data (MNFI)"""
    # stand volume [m3ha-1]
    vol, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'tilavuus.asc'), setnans=False)
    vol = vol*cmask

    # indexes for cells not recognized in mNFI
    ix_n = np.where((vol >= 32727) | (vol == -9999) )  # no satellite cover or not forest land: assign arbitrary values 
    ix_p = np.where((vol >= 32727) & (peatm == 1))  # open peatlands: assign arbitrary values
    ix_w = np.where((vol >= 32727) & (stream == 1))  # waterbodies: leave out
    cmask[ix_w] = np.nan  # NOTE: leaves waterbodies out of catchment mask
    vol[ix_n] = nofor['vol']
    vol[ix_p] = opeatl['vol']
    vol[ix_w] = np.nan

    #pine volume [m3 ha-1]
    p_vol, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname +'manty.asc'))
    p_vol = p_vol*cmask
    #spruce volume [m3 ha-1]
    s_vol, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname +'kuusi.asc'))
    s_vol = s_vol*cmask
    #birch volume [m3 ha-1]
    b_vol, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname +'koivu.asc'))
    b_vol = b_vol*cmask
    

    # basal area [m2 ha-1]
    ba, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'ppa.asc') )
    ba[ix_n] = nofor['ba']
    ba[ix_p] = opeatl['ba']
    ba[ix_w] = np.nan

    # tree height [m]
    height, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'keskipituus.asc'))
    height = 0.1*height  # m
    height[ix_n] = nofor['height']
    height[ix_p] = opeatl['height']
    height[ix_w] = np.nan

    # canopy closure [-]    
    cf, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'latvuspeitto.asc'))
    cf = 1e-2*cf
    cf[ix_n] = nofor['cf']
    cf[ix_p] = opeatl['cf']
    cf[ix_w] = np.nan
    # cfd, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'lehtip_latvuspeitto.asc'))
    # cfd = 1e-2*cfd  # percent to fraction

    # stand age [yrs]
    age, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname+'ika.asc'))
    age[ix_n] = nofor['age']
    age[ix_p] = opeatl['age']
    age[ix_w] = np.nan

    # leaf biomasses and one-sided LAI
    bmleaf_pine, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'bm_manty_neulaset.asc'))
    bmleaf_spruce, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'bm_kuusi_neulaset.asc'))
    bmleaf_decid, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'bm_lehtip_neulaset.asc'))
    # bmleaf_pine[ix_n]=np.nan; bmleaf_spruce[ix_n]=np.nan; bmleaf_decid[ix_n]=np.nan;

    LAI_pine = 1e-3*bmleaf_pine*SLA['pine']  # 1e-3 converts 10kg/ha to kg/m2
    LAI_pine[ix_n] = nofor['LAIpine']
    LAI_pine[ix_p] = opeatl['LAIpine']
    LAI_pine[ix_w] = np.nan

    LAI_spruce = 1e-3*bmleaf_spruce*SLA['spruce']
    LAI_spruce[ix_n] = nofor['LAIspruce']
    LAI_spruce[ix_p] = opeatl['LAIspruce']
    LAI_spruce[ix_w] = np.nan

    LAI_decid = 1e-3*bmleaf_decid*SLA['decid']
    LAI_decid[ix_n] = nofor['LAIdecid']
    LAI_decid[ix_p] = opeatl['LAIdecid']
    LAI_decid[ix_w] = np.nan

    bmroot_pine, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'bm_manty_juuret.asc'))
    bmroot_spruce, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'bm_kuusi_juuret.asc'))
    bmroot_decid, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'bm_lehtip_juuret.asc'))  
    bmroot = 1e-2*(bmroot_pine + bmroot_spruce + bmroot_decid)  # 1000 kg/ha
    bmroot[ix_n] = nofor['bmroot']
    bmroot[ix_p] = opeatl['bmroot']
    bmroot[ix_w] = np.nan
    # site types
    maintype, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'paatyyppi.asc'))
    maintype = maintype*cmask
    sitetype, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname + 'kasvupaikka.asc'))
    sitetype = sitetype*cmask
    #HERE DUPLICATE, REMOVE LATER    
    #site main class: 1- mineral soil; 2-spruce fen; 3-pine bog; 4-open peatland
    smc, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname +'paatyyppi.asc'))
    smc = smc*cmask
    #site fertility class: 1- ... 8 (1 Lehdot, 2 OMT, 3 MT, 4...)
    sfc, _, _, _, _ = read_AsciiGrid(os.path.join(fpath, bname +'kasvupaikka.asc'))
    sfc = sfc*cmask
    # downslope distance
     
    dsdist, _, _, _, _  = read_AsciiGrid(os.path.join(fpath, bname +'downslope_distance_16m.asc'))
    
    # catchment outlet location and catchment mean elevation
    (iy, ix) = np.where(flowacc == np.nanmax(flowacc))
    loc = {'lat': lat0[iy], 'lon': lon0[ix], 'elev': np.nanmean(dem)}
    # dict of all rasters
    GisData = {'cmask': cmask, 'dem': dem, 'flowacc': flowacc, 'slope': slope,
               'twi': twi, 'gtk_soilcode': gtk_s, 'soilclass': soil, 'peatm': peatm, 'stream': stream,
               'rockm': rockm, 'LAI_pine': LAI_pine, 'LAI_spruce': LAI_spruce,
               'LAI_conif': LAI_pine + LAI_spruce, 'smc':smc, 'sfc': sfc, 'soil':soil,
               'LAI_decid': LAI_decid, 'bmroot': bmroot, 'ba': ba, 'hc': height,
               'vol': vol, 'p_vol':p_vol,'s_vol':s_vol,'b_vol':b_vol,'cf': cf, 'age': age, 'maintype': maintype, 'sitetype': sitetype,
               'cellsize': cellsize, 'info': info, 'lat0': lat0, 'lon0': lon0, 'loc': loc, 'dsdist':dsdist}   

    if plotgrids is True:
        # %matplotlib qt
        # xx, yy = np.meshgrid(lon0, lat0)
        plt.close('all')

        plt.figure()

        plt.subplot(221)
        plt.imshow(dem); plt.colorbar(); plt.title('DEM (m)')
        plt.plot(ix, iy,'rs')
        plt.subplot(222)
        plt.imshow(twi); plt.colorbar(); plt.title('TWI')
        plt.subplot(223)
        plt.imshow(slope); plt.colorbar(); plt.title('slope(deg)')
        plt.subplot(224)
        plt.imshow(flowacc); plt.colorbar(); plt.title('flowacc (m2)')

        plt.figure(figsize=(6, 14))

        plt.subplot(221)
        plt.imshow(soil); plt.colorbar(); plt.title('soiltype')
        mask = cmask.copy()*0.0
        mask[np.isfinite(peatm)] = 1
        mask[np.isfinite(rockm)] = 2
        mask[np.isfinite(stream)] = 3

        plt.subplot(222)
        plt.imshow(mask); plt.colorbar(); plt.title('masks')
        plt.subplot(223)
        plt.imshow(LAI_pine+LAI_spruce + LAI_decid); plt.colorbar(); plt.title('LAI (m2/m2)')
        plt.subplot(224)
        plt.imshow(cf); plt.colorbar(); plt.title('cf (-)')

        
        plt.figure(figsize=(6,11))
        plt.subplot(321)
        plt.imshow(vol); plt.colorbar(); plt.title('vol (m3/ha)')
        plt.subplot(323)
        plt.imshow(height); plt.colorbar(); plt.title('hc (m)')
        #plt.subplot(223)
        #plt.imshow(ba); plt.colorbar(); plt.title('ba (m2/ha)')
        plt.subplot(325)
        plt.imshow(age); plt.colorbar(); plt.title('age (yr)')
        plt.subplot(322)
        plt.imshow(1e-3*bmleaf_pine); plt.colorbar(); plt.title('pine needles (kg/m2)')
        plt.subplot(324)
        plt.imshow(1e-3*bmleaf_spruce); plt.colorbar(); plt.title('spruce needles (kg/m2)')
        plt.subplot(326)
        plt.imshow(1e-3*bmleaf_decid); plt.colorbar(); plt.title('decid. leaves (kg/m2)')

    if plotdistr is True:
        twi0 = twi[np.isfinite(twi)]
        vol = vol[np.isfinite(vol)]
        lai = LAI_pine + LAI_spruce + LAI_decid
        lai = lai[np.isfinite(lai)]
        soil0 = soil[np.isfinite(soil)]
        
        plt.figure(100)
        plt.subplot(221)
        plt.hist(twi0, bins=100, color='b', alpha=0.5, normed=True)
        plt.ylabel('f');plt.ylabel('twi')

        s = np.unique(soil0)
        colcode = 'rgcym'
        for k in range(0,len(s)):
            # print k
            a = twi[np.where(soil==s[k])]
            a = a[np.isfinite(a)]
            plt.hist(a, bins=50, alpha=0.5, color=colcode[k], normed=True, label='soil ' +str(s[k]))
        plt.legend()
        plt.show()

        plt.subplot(222)
        plt.hist(vol, bins=100, color='k', normed=True); plt.ylabel('f'); plt.ylabel('vol')
        plt.subplot(223)
        plt.hist(lai, bins=100, color='g', normed=True); plt.ylabel('f'); plt.ylabel('lai')
        plt.subplot(224)
        plt.hist(soil0, bins=5, color='r', normed=True); plt.ylabel('f');plt.ylabel('soiltype')

    return GisData

def preprocess_soildata(pbu, psoil, soiltype, cmask, spatial=True):
    """
    creates input dictionary for initializing BucketGrid
    Args:
        bbu - bucket parameters dict
        psoil - soiltype dict
        soiltype - soiltype code classified into 5 groups
        cmask - catchment mask
    """
    # create dict for initializing soil bucket.
    # copy pbu into sdata and make each value np.array(np.shape(cmask))
    data = pbu.copy()
    data.update((x, y*cmask) for x, y in data.items())

    if spatial:
        for key in psoil.keys():
            c = psoil[key]['soil_id']
            ix = np.where(soiltype == c)
            data['poros'][ix] = psoil[key]['poros']
            data['fc'][ix] = psoil[key]['fc']
            data['wp'][ix] = psoil[key]['wp']
            data['ksat'][ix] = psoil[key]['ksat']
            data['beta'][ix] = psoil[key]['beta']
            del ix

        data['soilcode'] = soiltype
    return data
    

""" ************ Reading and writing Ascii -grids ********* """   
 
def read_AsciiGrid(fname, setnans=True):
    
    """ reads AsciiGrid format in fixed format as below:
    
        ncols         750
        nrows         375
        xllcorner     350000
        yllcorner     6696000
        cellsize      16
        NODATA_value  -9999
        -9999 -9999 -9999 -9999 -9999
        -9999 4.694741 5.537514 4.551162
        -9999 4.759177 5.588773 4.767114
    IN:
        fname - filename (incl. path)
    OUT:
        data - 2D numpy array
        info - 6 first lines as list of strings
        (xloc,yloc) - lower left corner coordinates (tuple)
        cellsize - cellsize (in meters?)
        nodata - value of nodata in 'data'
    Samuli Launiainen Luke 7.9.2016
    """
    import numpy as np
    fid = open(fname, 'r')
    info = fid.readlines()[0:6]
    fid.close()

    # print info
    # conversion to float is needed for non-integers read from file...
    xloc = float(info[2].split(' ')[-1])
    yloc = float(info[3].split(' ')[-1])
    cellsize = float(info[4].split(' ')[-1])
    nodata = float(info[5].split(' ')[-1])

    # read rest to 2D numpy array
    data = np.loadtxt(fname, skiprows=6)

    if setnans is True:
        data[data == nodata] = np.nan
        nodata = np.nan
    return data, info, (xloc, yloc), cellsize, nodata


def write_AsciiGrid(fname, data, info, fmt='%.18e'):
    """ writes AsciiGrid format txt file
    IN:
        fname - filename
        data - data (numpy array)
        info - info-rows (list, 6rows)
        fmt - output formulation coding
        
    Samuli Launiainen Luke 7.9.2016
    """
    import numpy as np

    # replace nans with nodatavalue according to info
    nodata = int(info[-1].split(' ')[-1])
    data[np.isnan(data)] = nodata
    # write info
    fid = open(fname, 'w')
    fid.writelines(info)
    fid.close()

    # write data
    fid = open(fname, 'a')
    np.savetxt(fid, data, fmt=fmt, delimiter=' ')
    fid.close()

""" ********* Flatten 2d array with nans to dense 1d array ********** """


def matrix_to_array(x, nodata=None):
    """ returns 1d array and their indices in original 2d array"""

    s = np.shape(x)
    if nodata is None:  # Nan
        ix = np.where(np.isfinite(x))
    else:
        ix = np.where(x != nodata)
    y = x[ix].copy()
    return y, ix, s


def array_to_matrix(y, ix, s, nodata=None):
    """returns 1d array reshaped into 2d array x of shape s"""
    if nodata is None:
        x = np.ones(s)*np.nan
    else:
        x = np.ones(s)*nodata
    x[ix] = y

    return x


def inputs_netCDF(ID, fname, data):
    """
    Store gridded data required by SpaFHy into netCDF 
    IN:
        ID -catchment id as str
        fname - filename
        data - dict with keys:
            cmask - catchment mask; integers within np.Nan outside
            LAI_conif [m2m-2]
            LAI_decid [m2m-2]
            hc, canopy closure [m]
            fc, canopy closure fraction [-]
            soil, soil type integer code 1-5
            flowacc - flow accumulation [units]
            slope - local surface slope [units]
            
            cellsize - gridcell size
            lon0 - x-grid
            lat0 - y-grid
    OUT:
        ncf - netCDF file handle. Initializes data
        ff - netCDF filename incl. path
    LAST EDIT 05.10.2018 / Samuli
    """

    from netCDF4 import Dataset #, date2num, num2date
    from datetime import datetime

    print('**** creating SpaFHy input netCDF4 file: ' + fname + ' ****')
    
    # create dataset & dimensions
    ncf = Dataset(fname, 'w')
    ncf.description = 'SpatialData from : ' + str(ID)
    ncf.history = 'created ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ncf.source = 'SpaFHy v.1.0 inputs'
    
    dlat, dlon = np.shape(data['cmask'])

    ncf.createDimension('dlon', int(dlon))
    ncf.createDimension('dlat', int(dlat))
    ncf.createDimension('scalar', 1)

    # create variables    
    # call as createVariable(varname,type,(dimensions))
    cellsize = ncf.createVariable('cellsize', 'f4', ('scalar',))
    cellsize.units = 'm'
    lat = ncf.createVariable('lat', 'f4', ('dlat',))
    lat.units = 'ETRS-TM35FIN'
    lon = ncf.createVariable('lon', 'f4', ('dlon',))
    lon.units = 'ETRS-TM35FIN'

    cellsize[0] = data['cellsize']
    lon[:] = data['lon0']
    lat[:] = data['lat0']
    
    # required inputs
    cmask = ncf.createVariable('cmask', 'i4', ('dlat','dlon',))
    cmask.units = 'integer inside catchment, Nan outside'
    LAI_conif = ncf.createVariable('LAI_conif', 'f4', ('dlat','dlon',))
    LAI_conif.units = 'conifer LAI (m2m-2)'
    LAI_decid = ncf.createVariable('LAI_decid', 'f4', ('dlat','dlon',))
    LAI_decid.units = 'deciduous annual max LAI (m2m-2)'    
    hc = ncf.createVariable('hc', 'f4', ('dlat','dlon',))
    hc.units = 'canopy height m'    
    cf = ncf.createVariable('cf', 'f4', ('dlat','dlon',))
    cf.units = 'canopy closure (-)' 
    
    soilclass = ncf.createVariable('soilclass', 'i4', ('dlat','dlon',))
    soilclass.units = 'soil class (1 - 5)'
    
    flowacc = ncf.createVariable('flowacc', 'f4', ('dlat','dlon',))
    flowacc.units = 'flow accumualtion area m2'
    slope = ncf.createVariable('slope', 'f4', ('dlat','dlon',))
    slope.units = 'local slope (deg)' 
    
    for k in ['LAI_conif', 'LAI_decid', 'hc', 'cf', 'soilclass', 'flowacc', 'slope']:
        ncf[k][:,:] = data[k]
    
    print('**** done  ****')


# specific for MEOLO-sites
""" ****************** creates gisdata dictionary from Vihti-koealue ************************ """

def create_vihti_catchment(ID='Vihti', fpath='c:\\projects\\fotetraf\\spathy\\data', plotgrids=False, plotdistr=False):
    """ 
    reads gis-data grids from selected catchments and returns numpy 2d-arrays
    IN: 
        ID - SVE catchment ID (int or str)
        fpath - folder (str)
        plotgrids - True plots
    OUT:
        GisData - dictionary with 2d numpy arrays and some vectors/scalars.

        keys [units]:'dem'[m],'slope'[deg],'soil'[coding 1-4], 'cf'[-],'flowacc'[m2], 'twi'[log m??],
        'vol'[m3/ha],'ba'[m2/ha], 'age'[yrs], 'hc'[m], 'bmroot'[1000kg/ha],'LAI_pine'[m2/m2 one-sided],'LAI_spruce','LAI_decid',
        'info','lat0'[latitude, euref_fin],'lon0'[longitude, euref_fin],loc[outlet coords,euref_fin],'cellsize'[cellwidth,m],
        'peatm','stream','cmask','rockm'[masks, 1=True]      
        
    TODO (6.2.2017 Samuli): 
        mVMI-datan koodit >32766 ovat vesialueita ja ei-metsäalueita (tiet, sähkölinjat, puuttomat suot) käytä muita maskeja (maastotietokanta, kysy
        Auralta tie + sähkölinjamaskit) ja IMPOSE LAI ja muut muuttujat ko. alueille. Nyt menevät no-data -luokkaan eikä oteta mukaan laskentaan.
    """
    from iotools import read_AsciiGrid

    fpath=os.path.join(fpath,str(ID)+'_')
                
    #specific leaf area (m2/kg) for converting leaf mass to leaf area        
    # SLA={'pine':5.54, 'spruce': 5.65, 'decid': 18.46} #m2/kg, Kellomäki et al. 2001 Atm. Env.
    SLA = {'pine': 6.8, 'spruce': 4.7, 'decid': 14.0}  # Härkönen et al. 2015 BER 20, 181-195

    #values to be set for 'open peatlands' and 'not forest land'
    nofor={'vol':0.1, 'ba':0.01, 'height':0.1, 'cf': 0.01, 'age': 0.0, 'LAIpine': 0.01, 'LAIspruce':0.01, 'LAIdecid': 0.01, 'bmroot':0.01}
    opeatl={'vol':0.01, 'ba':0.01, 'height':0.1, 'cf': 0.1, 'age': 0.0, 'LAIpine': 0.01, 'LAIspruce':0.01, 'LAIdecid': 0.01, 'bmroot':0.01}
    
    #dem, set values outside boundaries to NaN 
    dem, info, pos, cellsize, nodata = read_AsciiGrid(fpath+'dem_16m.asc')
    #latitude, longitude arrays    
    nrows, ncols=np.shape(dem)    
    lon0=np.arange(pos[0], pos[0]+cellsize*ncols,cellsize)
    lat0=np.arange(pos[1], pos[1]+cellsize*nrows,cellsize)
    lat0=np.flipud(lat0) #why this is needed to get coordinates correct when plotting?

    #catchment mask cmask ==1, np.nan outside
    cmask=dem.copy(); cmask[np.isfinite(cmask)]=1.0
    
    #flowacc, D-infinity, nr of draining cells
    flowacc, _, _, _, _ = read_AsciiGrid(fpath +'flowaccum_16m.asc')
    conv = np.nanmin(flowacc)  # to correct units in file
    flowacc = flowacc / conv *cellsize**2 #in m2
    #slope, degrees
    slope, _, _, _, _ = read_AsciiGrid(fpath + 'slope_16m.asc')
    #twi
    twi, _, _, _, _ = read_AsciiGrid(fpath + 'twi_16m.asc')
    
    #Maastotietokanta water bodies: 1=waterbody
    stream, _, _, _, _ = read_AsciiGrid(fpath +'vesielementit_1_0.asc')
    stream[stream == 0.0] = np.nan
    stream[np.isfinite(stream)]=1.0    
    #maastotietokanta peatlandmask
    #peatm, _, _, _, _ = read_AsciiGrid(fpath + 'suo_mtk.asc')
    peatm = np.ones([nrows, ncols])*np.nan
    #peatm[np.isfinite(peatm)]=1.0   
    #maastotietokanta kalliomaski
    #rockm, _, _, _, _ = read_AsciiGrid(fpath +'kallioalue_mtk.asc')
    #rockm[np.isfinite(rockm)]=1.0        
    rockm = peatm.copy()
            
    """ stand data (MNFI)"""

    #stand volume [m3ha-1]
    vol, _, _, _, _ = read_AsciiGrid(fpath +'tilavuus.asc', setnans=False)
    vol=vol*cmask
    #indexes for cells not recognized in mNFI
    ix_n=np.where((vol>=32727) | (vol==-9999) ) #no satellite cover or not forest land: assign arbitrary values 
    ix_p=np.where((vol>=32727) & (peatm==1))#open peatlands: assign arbitrary values
    ix_w=np.where((vol>=32727) & (stream==1)) #waterbodies: leave out
    cmask[ix_w]=np.nan #*********** NOTE: leave waterbodies out of catchment mask !!!!!!!!!!!!!!!!!!!!!!
    vol[ix_n]=nofor['vol']; vol[ix_p]=opeatl['vol']; vol[ix_w]=np.nan
    #basal area [m2 ha-1]
    ba, _, _, _, _ = read_AsciiGrid(fpath +'ppa.asc') 
    ba[ix_n]=nofor['ba']; ba[ix_p]=opeatl['ba']; ba[ix_w]=np.nan
    
   #tree height [m]
    height, _, _, _, _ = read_AsciiGrid(fpath +'keskipituus.asc')
    height=0.1*height #m  
    height[ix_n]=nofor['height']; height[ix_p]=opeatl['height']; height[ix_w]=np.nan
    
    #canopy closure [-]    
    cf, _, _, _, _ = read_AsciiGrid(fpath +'latvuspeitto.asc')   
    cfd, _, _, _, _ = read_AsciiGrid(fpath +'lehtip_latvuspeitto.asc')
    cf=1e-2*cf; cfd=1e-2*cfd; #in fraction
    cf[ix_n]=nofor['cf']; cf[ix_p]=opeatl['cf']; cf[ix_w]=np.nan
    
    #stand age [yrs]
    age, _, _, _, _ = read_AsciiGrid(fpath +'ika.asc')
    age[ix_n]=nofor['age']; age[ix_p]=opeatl['age']; age[ix_w]=np.nan
    
    #leaf biomasses and one-sided LAI
    bmleaf_pine, _, _, _, _ = read_AsciiGrid(fpath +'bm_manty_neulaset.asc')
    bmleaf_spruce, _, _, _, _ = read_AsciiGrid(fpath +'bm_kuusi_neulaset.asc')
    bmleaf_decid, _, _, _, _ = read_AsciiGrid(fpath +'bm_lehtip_neulaset.asc')
   # bmleaf_pine[ix_n]=np.nan; bmleaf_spruce[ix_n]=np.nan; bmleaf_decid[ix_n]=np.nan;
    
    LAI_pine=1e-3*bmleaf_pine*SLA['pine'] #1e-3 converts 10kg/ha to kg/m2
    LAI_pine[ix_n]=nofor['LAIpine']; LAI_pine[ix_p]=opeatl['LAIpine']; age[ix_w]=np.nan
    
    LAI_spruce=1e-3*bmleaf_spruce*SLA['spruce'] #1e-3 converts 10kg/ha to kg/m2
    LAI_spruce[ix_n]=nofor['LAIspruce']; LAI_spruce[ix_p]=opeatl['LAIspruce']; age[ix_w]=np.nan
    
    LAI_conif = LAI_spruce + LAI_pine
    
    LAI_decid=1e-3*bmleaf_decid*SLA['decid'] #1e-3 converts 10kg/ha to kg/m2
    LAI_decid[ix_n]=nofor['LAIdecid']; LAI_decid[ix_p]=opeatl['LAIdecid']; age[ix_w]=np.nan        
    
    bmroot_pine, _, _, _, _ = read_AsciiGrid(fpath +'bm_manty_juuret.asc')
    bmroot_spruce, _, _, _, _ = read_AsciiGrid(fpath +'bm_kuusi_juuret.asc')
    bmroot_decid, _, _, _, _ = read_AsciiGrid(fpath +'bm_lehtip_juuret.asc')         
    bmroot=1e-2*(bmroot_pine + bmroot_spruce + bmroot_decid) #1000 kg/ha 
    bmroot[ix_n]=nofor['bmroot']; bmroot[ix_p]=opeatl['bmroot']; age[ix_w]=np.nan    
    
    """
    gtk soilmap: read and re-classify into 4 texture classes
    #GTK-pintamaalaji grouped to 4 classes (Samuli Launiainen, Jan 7, 2017)
    #Codes based on maalaji 1:20 000 AND ADD HERE ALSO 1:200 000
    """
    CoarseTextured = [195213,195314,19531421,195313,195310]
    MediumTextured = [195315,19531521,195215,195214,195601,195411,195112,195311,195113,195111,195210,195110,195312]
    FineTextured = [19531521, 195412,19541221,195511,195413,195410,19541321,195618]
    Peats = [195512,195513,195514,19551822,19551891,19551892]
    Water =[195603]

    gtk_s, _, _, _, _ = read_AsciiGrid(fpath +'soil.asc') 

    r,c=np.shape(gtk_s);
    soil=np.ravel(gtk_s); del gtk_s
    soil[np.in1d(soil, CoarseTextured)]=1.0 #; soil[f]=1; del f
    soil[np.in1d(soil, MediumTextured)]=2.0
    soil[np.in1d(soil, FineTextured)]=3.0
    soil[np.in1d(soil, Peats)]=4.0
    soil[np.in1d(soil, Water)]=-1.0
        
    #soil[soil>4.0]=-1.0;
    #reshape back to original grid
    soil=soil.reshape(r,c)*cmask; del r,c
    soil[np.isfinite(peatm)]=4.0
    #update waterbody mask    
    ix=np.where(soil==-1.0)
    stream[ix]=1.0     

    # update catchment mask so that water bodies are left out (SL 20.2.18)
    #cmask[soil == -1.0] = np.nan
    cmask[soil <= 0] = np.nan
    soil = soil * cmask
    
    #catchment outlet location
    (iy,ix)=np.where(flowacc==np.nanmax(flowacc));
    loc={'lat':lat0[iy],'lon':lon0[ix],'elev': np.nanmean(dem)}
    
    # harvester driving route and location of test sites

    route, _, _, _, _ = read_AsciiGrid(fpath +'route.asc')
    test_sites, _, _, _, _ = read_AsciiGrid(fpath +'test_sites.asc')
          
    GisData={'cmask':cmask, 'dem':dem, 'flowacc': flowacc, 'slope': slope, 'twi': twi, 'soilclass':soil,
             'peatm':peatm, 'stream': stream, 'rockm': rockm,'LAI_pine': LAI_pine,
             'LAI_spruce': LAI_spruce, 'LAI_conif': LAI_conif, 'LAI_decid': LAI_decid,
             'bmroot': bmroot, 'ba': ba, 'hc': height, 'vol':vol,'cf':cf, 'cfd': cfd,
             'age': age, 'route': route, 'test_sites': test_sites, 
             'cellsize': cellsize, 'info': info, 'lat0':lat0, 'lon0':lon0,'loc':loc}   

    if plotgrids is True:
        #%matplotlib qt
        #xx,yy=np.meshgrid(lon0, lat0)
        plt.close('all')
        
        plt.figure()        
        plt.subplot(221);plt.imshow(dem); plt.colorbar(); plt.title('DEM (m)');plt.plot(ix,iy,'rs')
        plt.subplot(222);plt.imshow(twi); plt.colorbar(); plt.title('TWI')
        plt.subplot(223);plt.imshow(slope); plt.colorbar(); plt.title('slope(deg)')
        plt.subplot(224);plt.imshow(flowacc); plt.colorbar(); plt.title('flowacc (m2)')
        #
        plt.figure()
        plt.subplot(221); plt.imshow(soil); plt.colorbar(); plt.title('soiltype')
        mask=cmask.copy()*0.0
        mask[np.isfinite(peatm)]=1; mask[np.isfinite(rockm)]=2; mask[np.isfinite(stream)]=3; 
        plt.subplot(222); plt.imshow(mask); plt.colorbar(); plt.title('masks')
        plt.subplot(223); plt.imshow(LAI_pine+LAI_spruce + LAI_decid); plt.colorbar(); plt.title('LAI (m2/m2)')
        plt.subplot(224); plt.imshow(cf); plt.colorbar(); plt.title('cf (-)')
        
        plt.figure()
        plt.subplot(221);plt.imshow(vol); plt.colorbar(); plt.title('vol (m3/ha)')
        plt.subplot(222);plt.imshow(height); plt.colorbar(); plt.title('hc (m)')
        plt.subplot(223);plt.imshow(ba); plt.colorbar(); plt.title('ba (m2/ha)')
        plt.subplot(224);plt.imshow(age); plt.colorbar(); plt.title('age (yr)')
    
    if plotdistr is True:
        plt.figure()        
        #twi
        twi0=twi[np.isfinite(twi)]; vol=vol[np.isfinite(vol)]; lai=LAI_pine + LAI_spruce + LAI_decid
        lai=lai[np.isfinite(lai)];soil0=soil[np.isfinite(soil)]
        
        plt.subplot(221); plt.hist(twi0,bins=100,color='b',alpha=0.5,normed=True); plt.ylabel('f');plt.ylabel('twi')
       
        s=np.unique(soil0); print(s)
        colcode='rgcym'
        for k in range(0,len(s)):
            print(k)
            a=twi[np.where(soil==s[k])]; a=a[np.isfinite(a)]
            plt.hist(a,bins=50,alpha=0.5,color=colcode[k], normed=True, label='soil ' +str(s[k]))
        plt.legend(); plt.show()
       
        plt.subplot(222); plt.hist(vol,bins=100,color='k',normed=True); plt.ylabel('f');plt.ylabel('vol')
        plt.subplot(223); plt.hist(lai,bins=100,color='g',normed=True); plt.ylabel('f');plt.ylabel('lai')
        plt.subplot(224); plt.hist(soil0, bins=5,color='r',normed=True); plt.ylabel('f');plt.ylabel('soiltype')

        
    return GisData
    
def create_kuru_catchment(ID='Kuru', fpath=None, plotgrids=False, plotdistr=False):
    """ 
    reads gis-data grids from selected catchments and returns numpy 2d-arrays
    IN: 
        ID - SVE catchment ID (int or str)
        fpath - filepath (str)
        plotgrids - True plots
    OUT:
        GisData - dictionary with 2d numpy arrays and some vectors/scalars.

        keys [units]:'dem'[m],'slope'[deg],'soil'[coding 1-4], 'cf'[-],'flowacc'[m2], 'twi'[log m??],
        'vol'[m3/ha],'ba'[m2/ha], 'age'[yrs], 'hc'[m], 'bmroot'[1000kg/ha],'LAI_pine'[m2/m2 one-sided],'LAI_spruce','LAI_decid',
        'info','lat0'[latitude, euref_fin],'lon0'[longitude, euref_fin],loc[outlet coords,euref_fin],'cellsize'[cellwidth,m],
        'peatm','stream','cmask','rockm'[masks, 1=True]      
        
    TODO (6.2.2017 Samuli): 
        mVMI-datan koodit >32766 ovat vesialueita ja ei-metsäalueita (tiet, sähkölinjat, puuttomat suot) käytä muita maskeja (maastotietokanta, kysy
        Auralta tie + sähkölinjamaskit) ja IMPOSE LAI ja muut muuttujat ko. alueille. Nyt menevät no-data -luokkaan eikä oteta mukaan laskentaan.
    """
    from iotools import read_AsciiGrid

    fpath=os.path.join(fpath,str(ID)+'_')
    print(fpath)            
    #specific leaf area (m2/kg) for converting leaf mass to leaf area        
    # SLA={'pine':5.54, 'spruce': 5.65, 'decid': 18.46} #m2/kg, Kellomäki et al. 2001 Atm. Env.
    SLA = {'pine': 6.8, 'spruce': 4.7, 'decid': 14.0}  # Härkönen et al. 2015 BER 20, 181-195

    #values to be set for 'open peatlands' and 'not forest land'
    nofor={'vol':0.1, 'ba':0.01, 'height':0.1, 'cf': 0.01, 'age': 0.0, 'LAIpine': 0.01, 'LAIspruce':0.01, 'LAIdecid': 0.01, 'bmroot':0.01}
    opeatl={'vol':0.01, 'ba':0.01, 'height':0.1, 'cf': 0.1, 'age': 0.0, 'LAIpine': 0.01, 'LAIspruce':0.01, 'LAIdecid': 0.01, 'bmroot':0.01}
    
    #dem, set values outside boundaries to NaN 
    dem, info, pos, cellsize, nodata = read_AsciiGrid(fpath+'dem_16m.asc')
    #latitude, longitude arrays    
    nrows, ncols=np.shape(dem)    
    lon0=np.arange(pos[0], pos[0]+cellsize*ncols,cellsize)
    lat0=np.arange(pos[1], pos[1]+cellsize*nrows,cellsize)
    lat0=np.flipud(lat0) #why this is needed to get coordinates correct when plotting?

    #catchment mask cmask ==1, np.nan outside
    cmask=dem.copy(); cmask[np.isfinite(cmask)]=1.0
    
    #flowacc, D-infinity, nr of draining cells
    flowacc, _, _, _, _ = read_AsciiGrid(fpath +'flowaccum_16m.asc')
    conv = np.nanmin(flowacc)  # to correct units in file
    flowacc = flowacc / conv *cellsize**2 #in m2
    #slope, degrees
    slope, _, _, _, _ = read_AsciiGrid(fpath + 'slope_16m.asc')
    #twi
    twi, _, _, _, _ = read_AsciiGrid(fpath + 'twi_16m.asc')
    
    #Maastotietokanta water bodies: 1=waterbody
    stream, _, _, _, _ = read_AsciiGrid(fpath +'vesielementit.asc')
    stream[stream == 0.0] = np.nan
    stream[np.isfinite(stream)]=1.0    
    #maastotietokanta peatlandmask
    #peatm, _, _, _, _ = read_AsciiGrid(fpath + 'suo_mtk.asc')
    peatm = np.ones([nrows, ncols])*np.nan
    #peatm[np.isfinite(peatm)]=1.0   
    #maastotietokanta kalliomaski
    rockm, _, _, _, _ = read_AsciiGrid(fpath +'kallioalue_16m.asc')
    rockm[np.isfinite(rockm)]=1.0        
    rockm = peatm.copy()
            
    """ stand data (MNFI)"""

    #stand volume [m3ha-1]
    vol, _, _, _, _ = read_AsciiGrid(fpath +'tilavuus.asc', setnans=False)
    vol=vol*cmask
    #indexes for cells not recognized in mNFI
    ix_n=np.where((vol>=32727) | (vol==-9999) ) #no satellite cover or not forest land: assign arbitrary values 
    ix_p=np.where((vol>=32727) & (peatm==1))#open peatlands: assign arbitrary values
    ix_w=np.where((vol>=32727) & (stream==1)) #waterbodies: leave out
    cmask[ix_w]=np.nan #*********** NOTE: leave waterbodies out of catchment mask !!!!!!!!!!!!!!!!!!!!!!
    vol[ix_n]=nofor['vol']; vol[ix_p]=opeatl['vol']; vol[ix_w]=np.nan
    #basal area [m2 ha-1]
    ba, _, _, _, _ = read_AsciiGrid(fpath +'ppa.asc') 
    ba[ix_n]=nofor['ba']; ba[ix_p]=opeatl['ba']; ba[ix_w]=np.nan
    
   #tree height [m]
    height, _, _, _, _ = read_AsciiGrid(fpath +'keskipituus.asc')
    height=0.1*height #m  
    height[ix_n]=nofor['height']; height[ix_p]=opeatl['height']; height[ix_w]=np.nan
    
    #canopy closure [-]    
    cf, _, _, _, _ = read_AsciiGrid(fpath +'latvuspeitto.asc')   
    cfd, _, _, _, _ = read_AsciiGrid(fpath +'lehtip_latvuspeitto.asc')
    cf=1e-2*cf; cfd=1e-2*cfd; #in fraction
    cf[ix_n]=nofor['cf']; cf[ix_p]=opeatl['cf']; cf[ix_w]=np.nan
    
    #stand age [yrs]
    age, _, _, _, _ = read_AsciiGrid(fpath +'ika.asc')
    age[ix_n]=nofor['age']; age[ix_p]=opeatl['age']; age[ix_w]=np.nan
    
    #leaf biomasses and one-sided LAI
    bmleaf_pine, _, _, _, _ = read_AsciiGrid(fpath +'bm_manty_neulaset.asc')
    bmleaf_spruce, _, _, _, _ = read_AsciiGrid(fpath +'bm_kuusi_neulaset.asc')
    bmleaf_decid, _, _, _, _ = read_AsciiGrid(fpath +'bm_lehtip_neulaset.asc')
   # bmleaf_pine[ix_n]=np.nan; bmleaf_spruce[ix_n]=np.nan; bmleaf_decid[ix_n]=np.nan;
    
    LAI_pine=1e-3*bmleaf_pine*SLA['pine'] #1e-3 converts 10kg/ha to kg/m2
    LAI_pine[ix_n]=nofor['LAIpine']; LAI_pine[ix_p]=opeatl['LAIpine']; age[ix_w]=np.nan
    
    LAI_spruce=1e-3*bmleaf_spruce*SLA['spruce'] #1e-3 converts 10kg/ha to kg/m2
    LAI_spruce[ix_n]=nofor['LAIspruce']; LAI_spruce[ix_p]=opeatl['LAIspruce']; age[ix_w]=np.nan
    
    LAI_conif = LAI_spruce + LAI_pine
    
    LAI_decid=1e-3*bmleaf_decid*SLA['decid'] #1e-3 converts 10kg/ha to kg/m2
    LAI_decid[ix_n]=nofor['LAIdecid']; LAI_decid[ix_p]=opeatl['LAIdecid']; age[ix_w]=np.nan        
    
    bmroot_pine, _, _, _, _ = read_AsciiGrid(fpath +'bm_manty_juuret.asc')
    bmroot_spruce, _, _, _, _ = read_AsciiGrid(fpath +'bm_kuusi_juuret.asc')
    bmroot_decid, _, _, _, _ = read_AsciiGrid(fpath +'bm_lehtip_juuret.asc')         
    bmroot=1e-2*(bmroot_pine + bmroot_spruce + bmroot_decid) #1000 kg/ha 
    bmroot[ix_n]=nofor['bmroot']; bmroot[ix_p]=opeatl['bmroot']; age[ix_w]=np.nan    
    
    """
    gtk soilmap: read and re-classify into 4 texture classes
    #GTK-pintamaalaji grouped to 4 classes (Samuli Launiainen, Jan 7, 2017)
    #Codes based on maalaji 1:20 000 AND ADD HERE ALSO 1:200 000
    """
    CoarseTextured = [195213,195314,19531421,195313,195310]
    MediumTextured = [195315,19531521,195215,195214,195601,195411,195112,195311,195113,195111,195210,195110,195312]
    FineTextured = [19531521, 195412,19541221,195511,195413,195410,19541321,195618]
    Peats = [195512, 195513, 195514, 19551820, 19551822, 19551890, 19551891, 19551892]
    Water =[195603]

    gtk_s, _, _, _, _ = read_AsciiGrid(fpath +'soil.asc') 
    
    r,c=np.shape(gtk_s);
    soil=np.ravel(gtk_s); del gtk_s
    soil[np.in1d(soil, CoarseTextured)]=1.0 #; soil[f]=1; del f
    soil[np.in1d(soil, MediumTextured)]=2.0
    soil[np.in1d(soil, FineTextured)]=3.0
    soil[np.in1d(soil, Peats)]=4.0
    soil[np.in1d(soil, Water)]=-1.0
        
    #soil[soil>4.0]=-1.0;
    #reshape back to original grid
    soil=soil.reshape(r,c)*cmask; del r,c
    soil[np.isfinite(peatm)]=4.0
    #update waterbody mask    
    ix=np.where(soil==-1.0)
    stream[ix]=1.0     
    
    # update catchment mask so that water bodies are left out (SL 20.2.18)
    #cmask[soil == -1.0] = np.nan
    cmask[soil <= 0] = np.nan
    soil = soil * cmask

    #catchment outlet location
    (iy,ix)=np.where(flowacc==np.nanmax(flowacc));
    loc={'lat':lat0[iy],'lon':lon0[ix],'elev': np.nanmean(dem)}
    
    # harvester driving route and location of test sites

    #route, _, _, _, _ = read_AsciiGrid(fpath +'route.asc')
    #test_sites, _, _, _, _ = read_AsciiGrid(fpath +'test_sites.asc')
          
    GisData={'cmask':cmask, 'dem':dem, 'flowacc': flowacc, 'slope': slope, 'twi': twi, 'soilclass':soil, 'peatm':peatm, 'stream': stream,\
    'rockm': rockm,'LAI_pine': LAI_pine, 'LAI_spruce': LAI_spruce, 'LAI_conif': LAI_conif, 'LAI_decid': LAI_decid, 'bmroot': bmroot, 'ba': ba, 'hc': height,\
    'vol':vol,'cf':cf, 'cfd': cfd,'age': age, 'cellsize': cellsize, 'info': info, 'lat0':lat0, 'lon0':lon0,'loc':loc}  # 'route': route, 'test_sites': test_sites,  

        

    if plotgrids is True:
        #%matplotlib qt
        #xx,yy=np.meshgrid(lon0, lat0)
        plt.close('all')
        
        plt.figure()        
        plt.subplot(221);plt.imshow(dem); plt.colorbar(); plt.title('DEM (m)');plt.plot(ix,iy,'rs')
        plt.subplot(222);plt.imshow(twi); plt.colorbar(); plt.title('TWI')
        plt.subplot(223);plt.imshow(slope); plt.colorbar(); plt.title('slope(deg)')
        plt.subplot(224);plt.imshow(flowacc); plt.colorbar(); plt.title('flowacc (m2)')
        #
        plt.figure()
        plt.subplot(221); plt.imshow(soil); plt.colorbar(); plt.title('soiltype')
        mask=cmask.copy()*0.0
        mask[np.isfinite(peatm)]=1; mask[np.isfinite(rockm)]=2; mask[np.isfinite(stream)]=3; 
        plt.subplot(222); plt.imshow(mask); plt.colorbar(); plt.title('masks')
        plt.subplot(223); plt.imshow(LAI_pine+LAI_spruce + LAI_decid); plt.colorbar(); plt.title('LAI (m2/m2)')
        plt.subplot(224); plt.imshow(cf); plt.colorbar(); plt.title('cf (-)')
        
        plt.figure()
        plt.subplot(221);plt.imshow(vol); plt.colorbar(); plt.title('vol (m3/ha)')
        plt.subplot(222);plt.imshow(height); plt.colorbar(); plt.title('hc (m)')
        plt.subplot(223);plt.imshow(ba); plt.colorbar(); plt.title('ba (m2/ha)')
        plt.subplot(224);plt.imshow(age); plt.colorbar(); plt.title('age (yr)')
    
    if plotdistr is True:
        plt.figure()        
        #twi
        twi0=twi[np.isfinite(twi)]; vol=vol[np.isfinite(vol)]; lai=LAI_pine + LAI_spruce + LAI_decid
        lai=lai[np.isfinite(lai)];soil0=soil[np.isfinite(soil)]
        
        plt.subplot(221); plt.hist(twi0,bins=100,color='b',alpha=0.5,normed=True); plt.ylabel('f');plt.ylabel('twi')
       
        s=np.unique(soil0); # print(s)
        colcode='rgcym'
        for k in range(0,len(s)):
            # print(k)
            a=twi[np.where(soil==s[k])]; a=a[np.isfinite(a)]
            plt.hist(a,bins=50,alpha=0.5,color=colcode[k], normed=True, label='soil ' +str(s[k]))
        plt.legend(); plt.show()
       
        plt.subplot(222); plt.hist(vol,bins=100,color='k',normed=True); plt.ylabel('f');plt.ylabel('vol')
        plt.subplot(223); plt.hist(lai,bins=100,color='g',normed=True); plt.ylabel('f');plt.ylabel('lai')
        plt.subplot(224); plt.hist(soil0, bins=5,color='r',normed=True); plt.ylabel('f');plt.ylabel('soiltype')

        
    return GisData

""" ********* Get Forcing data: SVE catchments ****** """

def read_FMI_weather(ID, start_date, end_date, sourcefile, CO2=380.0):
    """
    reads FMI interpolated daily weather data from file
    IN:
        ID - sve catchment ID. set ID=0 if all data wanted
        start_date - 'yyyy-mm-dd'
        end_date - 'yyyy-mm-dd'
        sourcefile - optional
        CO2 - atm. CO2 concentration (float), optional
    OUT:
        fmi - pd.dataframe with datetimeindex
            fmi columns:['ID','Kunta','aika','lon','lat','T','Tmax','Tmin',
                         'Prec','Rg','h2o','dds','Prec_a','Par',
                         'RH','esa','VPD','doy']
            units: T, Tmin, Tmax, dds[degC], VPD, h2o,esa[kPa],
            Prec, Prec_a[mm], Rg,Par[Wm-2],lon,lat[deg]
    """
    
    # OmaTunniste;OmaItä;OmaPohjoinen;Kunta;siteid;vuosi;kk;paiva;longitude;latitude;t_mean;t_max;t_min;
    # rainfall;radiation;hpa;lamposumma_v;rainfall_v;lamposumma;lamposumma_cum
    # -site number
    # -date (yyyy mm dd)
    # -latitude (in KKJ coordinates, metres)
    # -longitude (in KKJ coordinates, metres)
    # -T_mean (degrees celcius)
    # -T_max (degrees celcius)
    # -T_min (degrees celcius)
    # -rainfall (mm)
    # -global radiation (per day in kJ/m2)
    # -H2O partial pressure (hPa)

    sourcefile = os.path.join(sourcefile)

    #ID = int(ID)

    # import forcing data
    fmi = pd.read_csv(sourcefile, sep=';', header='infer', 
                      usecols=['OmaTunniste', 'Kunta', 'aika', 'longitude',
                      'latitude', 't_mean', 't_max', 't_min', 'rainfall',
                      'radiation', 'hpa', 'lamposumma_v', 'rainfall_v'],
                      parse_dates=['aika'],encoding="ISO-8859-1")
    
    time = pd.to_datetime(fmi['aika'], format='%Y%m%d')

    fmi.index = time
    fmi = fmi.rename(columns={'OmaTunniste': 'ID', 'longitude': 'lon',
                              'latitude': 'lat', 't_mean': 'T', 't_max': 'Tmax',
                              't_min': 'Tmin', 'rainfall': 'Prec',
                              'radiation': 'Rg', 'hpa': 'h2o', 'lamposumma_v': 'dds',
                              'rainfall_v': 'Prec_a'})
    
    fmi['h2o'] = 1e-1*fmi['h2o']  # hPa-->kPa
    fmi['Rg'] = 1e3 / 86400.0*fmi['Rg']  # kJ/m2/d-1 to Wm-2
    fmi['Par'] = 0.5*fmi['Rg']

    # saturated vapor pressure
    esa = 0.6112*np.exp((17.67*fmi['T']) / (fmi['T'] + 273.16 - 29.66))  # kPa
    vpd = esa - fmi['h2o']  # kPa
    vpd[vpd < 0] = 0.0
    rh = 100.0*fmi['h2o'] / esa
    rh[rh < 0] = 0.0
    rh[rh > 100] = 100.0

    fmi['RH'] = rh
    fmi['esa'] = esa
    fmi['VPD'] = vpd

    fmi['doy'] = fmi.index.dayofyear
    fmi = fmi.drop(['aika'], axis=1)
    # replace nan's in prec with 0.0
    #fmi['Prec'][np.isnan(fmi['Prec'])] = 0.0
    fmi['Prec']= fmi['Prec'].fillna(value=0.0)
    # add CO2 concentration to dataframe
    fmi['CO2'] = float(CO2)
    
    # get desired period
    fmi = fmi[(fmi.index >= start_date) & (fmi.index <= end_date)]
#    if ID > 0:
#        fmi = fmi[fmi['ID'] == ID]
    return fmi

""" get forcing data from climate projections (120 years) """
def read_climate_prj(ID, start_date, end_date, sourcefile='c:\\Datat\\ClimateScenarios\\CanESM2.rcp45.csv'):
    #sourcefile = 'c:\\Datat\\ClimateScenarios\\CanESM2.rcp45.csv'

    # catchment id:climategrid_id
    grid_id = {1: 3211, 2: 5809, 3: 6170, 6: 6069, 7: 3150, 8: 3031, 9: 5349, 10: 7003, 11: 3375,
               12: 3879, 13: 3132, 14: 3268, 15: 2308, 16: 5785, 17: 6038, 18: 4488, 19: 3285,
               20: 6190, 21: 5818, 22: 5236, 23: 4392, 24: 4392, 25: 4960, 26: 1538, 27: 5135,
               28: 2059, 29: 4836, 30: 2438, 31: 2177, 32: 2177, 33: 5810}
               # 100: 6050, 101: 5810, 104: 6050, 105: 5810, 106: 5810}

    ID = int(ID)
    g_id = grid_id[ID]

    c_prj = pd.read_csv(sourcefile, sep=';', header='infer',
                        usecols=['id', 'rday', 'PAR', 'TAir','VPD', 'Precip', 'CO2'], parse_dates=False)                          
    c_prj = c_prj[c_prj['id'] == int(g_id)]
    time = pd.date_range('1/1/1980', '31/12/2099', freq='D')
    index = np.empty(30, dtype=int)
    dtime = np.empty(len(c_prj), dtype='datetime64[s]')
    j = 0; k = 0
    for i, itime in enumerate(time):
        if (itime.month == 2 and itime.day == 29):
            index[j] = i
            j = j + 1
        else: 
            dtime[k] = itime.strftime("%Y-%m-%d")
            k = k + 1
    c_prj.index = dtime
    
    c_prj['PAR'] = (1e6/86400.0/4.56)*c_prj['PAR']  # [mol/m-2/d] to Wm-2
    c_prj['Rg'] = 2.0*c_prj['PAR']
    c_prj['doy'] = c_prj.index.dayofyear

    # now return wanted period and change column names to standard
    dat = c_prj[(c_prj.index >= start_date) & (c_prj.index <= end_date)]
    dat = dat.rename(columns={'PAR': 'Par', 'Precip': 'Prec', 'TAir': 'T'})

    return dat

""" ************ Get Runoffs from SVE catchments ******* """


def read_SVE_runoff(ID, start_date,end_date, sourcefile):
    """
    reads FMI interpolated daily weather data from file
    IN:
        ID - sve catchment ID. str OR list of str (=many catchments)
        start_date - 'yyyy-mm-dd'
        end_date - 'yyyy-mm-dd'
        sourcefile - optional
    OUT:
        roff - pd.dataframe with datetimeindex
            columns: measured runoff (mm/d)
            if ID=str, then column is 'Qm'
            if ID = list of str, then column is catchment ID
            MISSING DATA = np.nan
    CODE: Samuli Launiainen (Luke, 7.2.2017)
    """
    # Runoffs compiled from Hertta-database (Syke) and Metla/Luke old observations.
    # Span: 1935-2015, missing data=-999.99
    # File columns:
    # pvm;14_Paunulanpuro;15_Katajaluoma;16_Huhtisuonoja;17_Kesselinpuro;18_Korpijoki;20_Vaarajoki;
    # 22_Vaha-Askanjoki;26_Iittovuoma;24_Kotioja;27_Laanioja;1_Lompolojanganoja;10_Kelopuro;
    # 13_Rudbacken;3_Porkkavaara;11_Hauklammenoja;19_Pahkaoja;21_Myllypuro;23_Ylijoki;2_Liuhapuro;
    # 501_Kauheanpuro;502_Korsukorvenpuro;503_Kangasvaaranpuro;504_Kangaslammenpuro;56_Suopuro;
    # 57_Valipuro;28_Kroopinsuo;30_Pakopirtti;31_Ojakorpi;32_Rantainrahka

    # import data
    sourcefile = os.path.join(sourcefile)
    dat = pd.read_csv(sourcefile, sep=';', header='infer', parse_dates=['pvm'], index_col='pvm', na_values=-999)

    # split column names so that they equal ID's
    cols = [x.split("_")[0] for x in dat.columns]
    dat.columns = cols

    # get desired period & rename column ID to Qm
    dat = dat[(dat.index >= start_date) & (dat.index <= end_date)]
    dat = dat[ID]
    if type(ID) is str:
        dat.columns = ['Qm']
    return dat


""" ************ SVE valuma-alueet: get data from Vesidata -database ********************** """

def vdataQuery(alue, alku, loppu, kysely, fname=None):
    """
    Runs Vesidata html standard queries    
    
    IN:
        alue - alueid (int)
        alku - '2015-05-25', (str)
        loppu -'2015-06-01', (str)
        kysely -'raw', 'wlevel', 'saa', (str)
        fname - filename for saving ascii-file
    OUT:
        dat - pd DataFrame; index is time and keys are from 1st line of query
    Samuli L. 25.4.2016; queries by Jukka Pöntinen & Anne Lehto
    
    käyttöesim1: https://taimi.in.metla.fi/cgi/bin/12.vesidata_haku.pl?id=3&alku=2016-01-25&loppu=2016-02-10&kysely=wlevel 
    käyttöesim2: https://taimi.in.metla.fi/cgi/bin/12.vesidata_haku.pl?id=Porkkavaara&alku=2016-01-25&loppu=2016-02-10&kysely=raw
    käyttöesim3: https://taimi.in.metla.fi/cgi/bin/12.vesidata_haku.pl?id=Porkkavaara&alku=2016-01-25&loppu=2016-02-10&kysely=saa
    
    vaaditaan parametrit:
    id = Alueen nimi tai numero, esim Kivipuro tai 33, joka on Kivipuron aluenumero, 
         annual-ryhmän kyselyyn voi antaa id=all, jolloin haetaan kaikki alueet
    
    alku = päivä,josta lähtien haetaan 2016-01-25
    
    loppu = päivä,johon saakka haetaan 2016-02-10
    
    kysely: 
    'wlevel' = haetaan vedenkorkeusmuuttujat tietyssä järjestyksessä
    'raw' = haetaan näiden lisäksi kaikki 'raw'-ryhmän muuttujat
    'saa' = haetaan päivittäinen sää, eli sademäärä ja keskilämpötila 
    'annual' = haetaan vuoden lasketut tulokset, päivämäärän alkupäivä on vuoden 1. päivä, loppupäivä esim. vuoden toinen päivä
    'craw'= haetaan kaikki tämän ryhmän muuttujat 
    'dload'= haetaan kaikki tämän ryhmän muuttujat 
    'roff'= haetaan kaikki tämän ryhmän muuttujat 
    'wquality'= haetaan kaikki tämän ryhmän muuttujat 

    """

    import urllib2, os, shutil
    import pandas as pd
    #addr='https://taimi.in.metla.fi/cgi/bin/12.vesidata_haku.pl?id=all&alku=2014-01-01&loppu=2014-10-25&kysely=annual' KAIKKI ANNUAL-MUUTTUJAT
    #addr='https://taimi.in.metla.fi/cgi/bin/vesidata_haku.pl?id=Liuhapuro&alku=2015-05-25&loppu=2015-06-10&kysely=raw'
    
    addr='https://taimi.in.metla.fi/cgi/bin/vesidata_haku.pl?id=%s&alku=%s&loppu=%s&kysely=%s' %(str(alue), alku, loppu, kysely)
    ou='tmp.txt'
    
    f=urllib2.urlopen(addr) #open url, read to list and close
    r=f.read().split("\n")
    f.close()
    
    g=open(ou, 'w') #open tmp file, write, close
    g.writelines("%s\n" % item for item in r)
    g.close()
    
    #read  'tmp.txt' back to dataframe
    if kysely == 'annual': #annual query has different format
        dat=pd.read_csv(ou)
        f=dat['v_alue_metodi']
        yr=[]; alue=[]; mtd=[]        
        for k in range(0, len(f)):
            yr.append(float(f[k].split('a')[0]))
            mtd.append(int(f[k].split('d')[1]))
            x=f[k].split('m')[0]
            alue.append(int(x.split('e')[1]))
        dat=dat.drop('v_alue_metodi',1)
        dat.insert(0,'alue_id', alue); dat.insert(1, 'vuosi',yr); dat.insert(2,'mtd', mtd)
        
    else: #...than the other queries
        dat=pd.read_csv(ou,index_col=0)
        dat.index=dat.index.to_datetime() #convert to datetime
    
    
    if kysely == 'wlevel': #manipulate column names
        cols=list(dat.columns.values)
        h=[]  
        for item in cols:
            h.append(item.split("=")[1])
        dat.columns=h
    
    if fname is not None: #copy to fname, remove ou
        shutil.copy(ou, fname)
    os.remove(ou)

    return dat    

""" ************************ Forcing data, sitefile ************************** """
def read_FMI_weatherdata(forcfile, fyear,lyear, asdict=False):
    """ 
    reads FMI interpolated daily weather data from file containing single point
    IN: 
        forcfile- filename 
        fyear & lyear - first and last years 
        asdict=True if dict output, else pd.dataframe
    OUT: F -pd.DataFrame with columns (or dict with fields):
        time, doy, Ta, Tmin, Tmax (degC), Prec (mm/d), Rg (Wm-2), VPD (kPa), RH (%), esa (kPa), h2o (kPa), dds (degC, degree-day sum)
        
    """
    
    #OmaTunniste;OmaItä;OmaPohjoinen;Kunta;siteid;vuosi;kk;paiva;longitude;latitude;t_mean;t_max;t_min;
    #rainfall;radiation;hpa;lamposumma_v;rainfall_v;lamposumma;lamposumma_cum
    #-site number
    #-date (yyyy mm dd)
    #-latitude (in KKJ coordinates, metres)
    #-longitude (in KKJ coordinates, metres)
    #-T_mean (degrees celcius)
    #-T_max (degrees celcius)
    #-T_min (degrees celcius)
    #-rainfall (mm)
    #-global radiation (per day in kJ/m2)
    #-H2O partial pressure (hPa)

    from datetime import datetime
    #forcfile='c:\\pyspace\\DATAT\\Topmodel_calibr\\FMI_saa_Porkkavaara.csv'

    #import forcing data
    dat=np.genfromtxt(forcfile,dtype=float,delimiter=';', usecols=(5,6,7,10,11,12,13,14,15,16))

    fi=np.where(dat[:,0]>=fyear); li=np.where(dat[:,0]<=lyear)
    ix=np.intersect1d(fi,li); #del fi, li
    #print min(ix), max(ix), np.shape(ix)
    tvec=dat[ix,0:3] #YYYY MM DD

    dat=dat[ix, 3:] 

    time=[]; doy=[]
    for k in range(0,len(tvec)):
        time.append(datetime( int(tvec[k,0]), int(tvec[k,1]), int(tvec[k,2]), 0, 0) )
        doy.append(time[k].timetuple().tm_yday)
    
    time=np.array(time)
    doy=np.array(doy)
    
    Ta=dat[:,0];Tmax=dat[:,1]; Tmin=dat[:,2]; Prec=dat[:,3]; Rg=1e3*dat[:,4]/86400.0;  Par=Rg*0.5 #from kJ/m2/d-1 to Wm-2 
    e=1e-1*dat[:,5]; #hPa-->kPa
    dds=dat[:,6] #temperature sum

    #saturated vapor pressure    
    esa=0.6112*np.exp((17.67*Ta)/ (Ta +273.16 -29.66))  #kPa
    vpd=esa - e; #kPa   
    vpd[vpd<0]=0.0
    rh=100.0*e/esa;
    rh[rh<0]=0.0; rh[rh>100]=100.0
                
    F={'Ta':Ta, 'Tmin':Tmin, 'Tmax':Tmax, 'Prec':Prec, 'Rg':Rg, 'Par': Par, 'VPD':vpd, 'RH':rh, 'esa':esa, 'h2o':e, 'dds':dds}

    F['time']=time
    F['doy']=doy
    
    ix=np.where(np.isnan(F['Prec'])); 
    F['Prec'][ix]=0.0
    #del dat, fields, n, k, time
    
    if asdict is not True:
        #return pandas dataframe
        F=pd.DataFrame(F)
        cols=['time', 'doy', 'Ta', 'Tmin','Tmax', 'Prec', 'Rg', 'Par',  'VPD', 'RH', 'esa', 'h2o', 'dds']
        F=F[cols]
    return F
        
"""  ******* functions to read Hyde data for CanopyGrid calibration ******** """


def read_HydeDaily(filename):

    cols=['time','doy','NEE','GPP','TER','ET','H','NEEflag','ETflag','Hflag','Par','Rnet','Ta','VPD','CO2','PrecSmear','Prec','U','Pamb',
    'SWE0','SWCh','SWCa','SWCb','SWCc', 'Tsh','Tsa','Tsb','Tsc','RnetFlag','Trfall','Snowdepth','Snowdepthstd','SWE','SWEstd','Roff1','Roff2']        
    
    dat=pd.read_csv(filename,sep='\s+',header=None, names=None, parse_dates=[[0,1,2]], keep_date_col=False)
    dat.columns=cols
    dat.index=dat['time']; dat=dat.drop(['time','SWE0'],axis=1)
    
    forc=dat[['doy','Ta','VPD','Prec','Par','U']]; forc['Par']= 1/4.6*forc['Par']; forc['Rg']=2.0*forc['Par']
    forc['VPD'][forc['VPD']<=0]=eps
    
    #relatively extractable water, Hyde A-horizon
    #poros = 0.45    
    fc = 0.30
    wp = 0.10
    Wliq = dat['SWCa']
    Rew = np.maximum( 0.0, np.minimum( (Wliq-wp)/(fc - wp + eps), 1.0) )
    forc['Rew'] = Rew
    forc['CO2'] = 380.0
    # beta, soil evaporation parameter 
    #forc['beta'] =  Wliq / fc
    return dat, forc
    
    
def read_CageDaily(filepath):
    
    cols=['time','doy','NEE','GPP','TER','ET','H','NEEflag','ETflag','Hflag','Par','Rnet','Ta','VPD','CO2','SWCa','PrecSmear','Prec','U','Pamb']        
    
    dat1=pd.read_csv(filepath + 'HydeCage4yr-2000.txt',sep='\s+',header=None, names=None, parse_dates=[[0,1,2]], keep_date_col=False)
    dat1.columns=cols
    dat1.index=dat1['time']; dat1=dat1.drop('time',axis=1)
    forc1=dat1[['doy','Ta','VPD','Prec','Par','U']]; forc1['Par']= 1/4.6*forc1['Par']; forc1['Rg']=2.0*forc1['Par']
    
    dat2=pd.read_csv(filepath + 'HydeCage12yr-2002.txt',sep='\s+',header=None, names=None, parse_dates=[[0,1,2]], keep_date_col=False)
    dat2.columns=cols
    dat2.index=dat2['time']; dat2=dat2.drop('time',axis=1)
    forc2=dat2[['doy','Ta','VPD','Prec','Par','U']]; forc2['Par']= 1/4.6*forc2['Par']; forc2['Rg']=2.0*forc2['Par']
    return dat1, dat2,forc1,forc2


def read_setup(inifile):
    """
    reads Spathy.ini parameter file into pp dict
    """
    # inifile = os.path.join(spathy_path, inifile)
    print(inifile)
    cfg = configparser.ConfigParser()
    cfg.read(inifile)

    pp = {}
    for s in cfg.sections():
        section = s.encode('ascii', 'ignore')
        pp[section] = {}
        for k, v in cfg.items(section):
            key = k.encode('ascii', 'ignore')
            val = v.encode('ascii', 'ignore')
            if section == 'General':  # 'general' section
                pp[section][key] = val
            else:
                pp[section][key] = float(val)
    pp['General']['dt'] = float(pp['General']['dt'])

    pgen = pp['General']
    pcpy = pp['CanopyGrid']
    pbu = pp['BucketGrid']
    ptop = pp['Topmodel']

    return pgen, pcpy, pbu, ptop


def get_clear_cuts(pgen, cmask):
    import os
    import datetime
    from calendar import monthrange
    
    clear_cuts ={}
    scens=[f for f in os.listdir(pgen['gis_scenarios']) if f.endswith('.asc')]
    if scens:
        for s in scens:
            m = s[4:6]        
            yr = s[:4]
            days = monthrange(int(yr), int(m))   #locate cuttings to the last day of month
            d = days[1] #s[6:8]    
            key=datetime.date(int(yr),int(m),int(d))
            cut, _, _, _, _ = read_AsciiGrid(pgen['gis_scenarios'] + s)
            ix = np.where(np.isfinite(cmask)) 
            cut2 = cut[ix].copy()
            clear_cuts[key]=cut2
    else:
        print ('No available clear-cut scenario rasters in ', pgen['gis_scenarios'])
        key=datetime.date(int(2900),int(12),int(31))
        cut = cmask.copy()
        ix = np.where(np.isfinite(cmask)) 
        cut2 = cut[ix].copy()
        cut2[:] = np.nan
        clear_cuts[key]=cut2.copy()
    return clear_cuts

def weather_fig(df):

    sns.set()
    #import string
    #printable = set(string.printable)
    fs=12
    fig = plt.figure(num='Susi - weather data', figsize=[15.,8.], facecolor='#C1ECEC')  #see hex color codes from https://www.rapidtables.com/web/color/html-color-codes.html
    municipality = df['Kunta'][0]   
    #fig.suptitle('Weather data, '+ filter(lambda x: x in printable, municipality), fontsize=18)
    ax1 = fig.add_axes([0.05,0.55,0.6,0.35])                             #left, bottom, width, height
    ax1.plot(df.index, df['Prec'].values, 'b-', label='Rainfall')
    ax1.set_xlabel('Time', fontsize=fs)
    ax1.set_ylabel('Rainfall, mm', fontsize=12)
    ax1.legend(loc='upper left')
    ax11 = ax1.twinx()
    ax11.plot(df.index, np.cumsum(df['Prec'].values), 'm-', linewidth=2., label='Cumulative rainfall')
    ax11.set_ylabel('Cumulative rainfall [mm]', fontsize = fs)
    ax11.legend(loc='upper right')

    annual_prec = df['Prec'].resample('A').sum()
    ax2 =fig.add_axes([0.73, 0.55, 0.25, 0.35])
    
    t1 = 'Mean annual rainfall ' + str(np.round(np.mean(annual_prec.values))) + ' mm'    
    ax2.set_title(t1, fontsize = 14)
    y_pos = np.arange((len(annual_prec)))
    plt.bar(y_pos, annual_prec.values, align='center', alpha = 0.5)    
    plt.xticks(y_pos, annual_prec.index.year, rotation = 45)
    ax2.set_ylabel('mm')

    zeroline =np.zeros(len(df.index))
    ax3 = fig.add_axes([0.05,0.08,0.6,0.35])
    ax3.plot(df.index, df['T'], 'g', linewidth = 0.5)
    ax3.plot(df.index, zeroline, 'b-')
    ax3.fill_between(df.index, df['T'],0, where=df['T']<0.0, facecolor='b', alpha=0.3)
    ax3.fill_between(df.index, df['T'],0, where=df['T']>=0.0, facecolor='r', alpha=0.3)
    ax3.set_ylabel('Air temperature, $^\circ$ C', fontsize = fs)

    annual_temp = df['T'].resample('A').mean()
    t2 = 'Mean annual temperature ' + str(np.round(np.mean(annual_temp.values), 2)) + '  $^\circ$ C'    
    
    ax4 =fig.add_axes([0.73, 0.08, 0.25, 0.35])
    ax4.set_title(t2, fontsize = 14)
    y_pos = np.arange((len(annual_temp)))
    plt.bar(y_pos, annual_temp.values, align='center', alpha = 0.5)    
    plt.xticks(y_pos, annual_temp.index.year, rotation = 45)
    ax4.set_ylabel(' $^\circ$ C', fontsize = fs)
    plt.show()
