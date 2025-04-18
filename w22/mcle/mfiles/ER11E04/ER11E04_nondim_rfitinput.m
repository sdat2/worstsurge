%ER11E04_nondim_rfitinput.m -- Chavas et al. 2015 profile merging ER11 and E04 solutions
%Purpose: Merge E04 and ER11 profiles for input (rfit,Vfit)
%
% Syntax:
%   [rr,VV,rfit,Vfit,rmerge,Vmerge,rrfracr0,MMfracM0,rmaxr0,MmM0,rmerger0,MmergeM0] = ...
%       ER11E04_nondim_rfitinput(Vmax,rfit,Vfit,fcor,Cdvary,C_d,w_cool,CkCdvary,CkCd,eye_adj,alpha_eye)
%
% Inputs:
%   Vmax [ms-1] - maximum wind speed
%   rfit [m] - a wind radius
%   Vfit [ms-1] - wind speed at rfit
%   fcor [s-1] - Coriolis parameter
%   Cdvary [] - 1=C_d varies following Donelan et al 2004; 0=input value
%   C_d [-] - drag coefficient in outer region; ignored if Cdvary = 1
%   w_cool [sm-1] - radiative-subsidence rate
%   CkCdvary [] - 1=C_k/C_d varies following quadratic fit to Vmax from Chavas et al. 2015; 0=input value
%   CkCd [-] - ratio of surface exchange coefficients of enthalpy and
%       momentum in inner region
%   eye_adj [-] - 0 = use ER11 profile in eye; 1 = empirical adjustment
%   alpha_eye [-] - V/Vm in eye is reduced by factor (r/rm)^alpha_eye; ignored if eye_adj=0
%
% Outputs:
%   rr [m] - vector of radii
%   VV [ms-1] - vector of wind speeds at rr
%   rmax [m] - radius of maximum wind
%   r0 [m] - outer radius where V=0
%   rmerge [m] - radius of merge point between inner and outer solutions
%   Vmerge [ms-1] - wind speed at rmerge
%   rrfracr0 [-] - vector of r/r0
%   MMfracM0 [-] - vector of M/M0 at rrfracr0
%   rmaxr0 [-] - rmax/r0
%   MmM0 [-] - M/M0 at rmaxr0
%   rmerger0 [-] - rmerge/r0
%   MmergeM0 [-] - M/M0 at rmerger0
%
% References: 
%   - Chavas et al., 2015
%   - Emanuel, K., and R. Rotunno, 2011: Self-Stratification of
%       Tropical Cyclone Outflow. Part I: Implications for Storm Structure.
%       J. Atmos. Sci., 68, 2236-2249.
%   - Emanuel, K., 2004:  Tropical Cyclone Energetics and Structure. In
%       Atmospheric Turbulence and Mesoscale Meteorology, E. Fedorovich,
%       R. Rotunno and B. Stevens, editors, Cambridge University Press,
%       280 pp.
%
% Other files required: included in subdirectory mfiles/

% Author: Dan Chavas
% CEE Dept, Princeton University
% email: drchavas@gmail.com
% Website: --
% 12 May 2015; Last revision:
%------------- BEGIN CODE --------------

function [rr,VV,rmax,r0,rmerge,Vmerge,rrfracr0,MMfracM0,rmaxr0,MmM0,rmerger0,MmergeM0] = ...
    ER11E04_nondim_rfitinput(Vmax,rfit,Vfit,fcor,Cdvary,C_d,w_cool,CkCdvary,CkCd,eye_adj,alpha_eye)

%% Check inputs
if(nargin<7)
    error('Not enough input arguments')
elseif(nargin==7)
    CkCdvary = 0;
    CkCd = 1;
    eye_adj = 0;
    alpha_eye = .15;
elseif(nargin==8)
    error('CkCdvary has been input, but not CkCd')
elseif(nargin==9)
    eye_adj = 0;
    alpha_eye = .15;
elseif(nargin==10)
    error('eye_adj has been input, but not alpha_eye')
end

%% Initialization
fcor = abs(fcor);

%% Overwrite CkCd if want varying (quadratic fit from Chavas et al. 2015)
if(CkCdvary == 1)
    CkCd_coefquad = 5.5041e-04;
    CkCd_coeflin = -0.0259;
    CkCd_coefcnst = 0.7627;
    CkCd = CkCd_coefquad.*Vmax.^2 + CkCd_coeflin.*Vmax + CkCd_coefcnst;
end

% if(CkCdvary==1 && CkCd<0.5)
%     %CkCd=0.498; %CkCd=0498 at Vmax = 15 m/s
%     CkCd=0.5; %CkCd=0498 at Vmax = 15 m/s
%     %sprintf('Ck/Cd is set to lower bound of 0.5.')
% end

if(CkCd>1.9)
    CkCd=1.9;
    sprintf('Ck/Cd is capped at 1.9 and has been set to this value. If CkCdvary=1, then Vmax is much greater than the range of data used to estimate CkCd as a function of Vmax -- here be dragons!')
end

Mfit = rfit*Vfit + .5*fcor*rfit.^2;

%% Loop through rmaxfracrfit values til converges to match (rfitr0,MfitM0)
soln_converged = 0;
while(soln_converged==0)

    rmaxrfit_min = .01;
    rmaxrfit_max = 1;
    rmaxrfit_new = (rmaxrfit_max+rmaxrfit_min)/2;    %first guess -- in the middle
    rmaxrfit = rmaxrfit_new;    %initialize
    drmaxrfit = rmaxrfit_max - rmaxrfit;    %initialize
    drmaxrfit_thresh = .0001;
    while(abs(drmaxrfit)>=drmaxrfit_thresh)  %keep looping til changes in estimate are very small

        rmax = rmaxrfit_new*rfit;

        %% Step 1: Calculate ER11 M/Mm vs. r/rm
        %[~,~,rrfracrm_ER11,MMfracMm_ER11] = ER11_radprof_nondim(Vmax,rmax,fcor,CkCdvary,CkCd);
        drfracrm = .01;
        if(rmax>100*1000)
            drfracrm = drfracrm/10; %extra precision for large storm
        end
        rfracrm_min = 0;   %[-]; start at r=0
        rfracrm_max = 50;    %[-]; extend out to many rmaxs
        rrfracrm_ER11 = rfracrm_min:drfracrm:rfracrm_max; %[]; r/r0 vector

        rr_ER11 = rrfracrm_ER11*rmax;
        rmax_or_r0 = 'rmax';
        [VV_ER11,~] = ER11_radprof(Vmax,rmax,rmax_or_r0,fcor,CkCd,rr_ER11);
        
        if(~isnan(max(VV_ER11)))    %ER11_radprof converged

            Mm = rmax*Vmax + .5*fcor*rmax.^2;
            MMfracMm_ER11 = (rr_ER11.*VV_ER11 + .5*fcor*rr_ER11.^2)./Mm;

            %% Step 2: Converge rmaxr0 geometrically until ER11 M/M0 has tangent point with E04 M/M0
            %%Break up interval into 3 points, take 2 between which intersection vanishes, repeat til converges
            rmaxr0_min = .01;
            rmaxr0_max = .75;
            rmaxr0_new = (rmaxr0_max+rmaxr0_min)/2;    %first guess -- in the middle
            rmaxr0 = rmaxr0_new;    %initialize
            drmaxr0 = rmaxr0_max - rmaxr0;    %initialize
            drmaxr0_thresh = .000001;
            iter = 0;
            while(abs(drmaxr0)>=drmaxr0_thresh)  %keep looping til changes in estimate are very small

                iter = iter + 1;

                %%Calculate E04 M/M0 vs r/r0
                r0 = rmax/rmaxr0_new;   %[m]
                Nr = 100000;
                [rrfracr0_E04,MMfracM0_E04] = E04_outerwind_r0input_nondim_MM0(r0,fcor,Cdvary,C_d,w_cool,Nr);

                %%Convert ER11 to M/M0 vs. r/r0 space
                rrfracr0_ER11 = rrfracrm_ER11*(rmaxr0_new);
                M0_E04 = .5*fcor*r0.^2;
                MMfracM0_ER11 = MMfracMm_ER11*(Mm/M0_E04);

                %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
                %%TESTING: Plot radial profile, mark rrad, and plot E04 model fits and rmaxs %%%%%%
                %{
                figure(1008)
                plot(rrfracr0_ER11,MMfracM0_ER11,'b')
                hold on
                plot(rrfracr0_E04,MMfracM0_E04,'Color',[1 0 0]/iter)
                axis([0 1 0 1])
                xlabel('r/r_0');
                ylabel('M/M_0');
                %}
                %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

                [X0,Y0] = curveintersect(rrfracr0_E04,MMfracM0_E04,rrfracr0_ER11,MMfracM0_ER11);
                if(numel(X0)==0)    %no intersections -- r0 too small --> rmaxr0 too large
                    drmaxr0 = abs(drmaxr0)/2;
                else    %at least one intersection -- r0 too large --> rmaxr0 too small
                    drmaxr0 = -abs(drmaxr0)/2;
                    rmerger0 = mean(X0);
                    MmergeM0 = mean(Y0);
                end

                %%update value of rmaxr0
                rmaxr0 = rmaxr0_new;    %this is the final one
                rmaxr0_new = rmaxr0_new + drmaxr0;

            end

            %% Calculate some things
            M0 = .5*fcor*r0^2;
            Mm = .5*fcor*rmax.^2 + rmax.*Vmax;
            MmM0 = Mm/M0;

            %% Define merged solution
            ii_ER11 = rrfracr0_ER11<rmerger0 & MMfracM0_ER11<MmergeM0;
            ii_E04 = rrfracr0_E04>=rmerger0 & MMfracM0_E04>MmergeM0;
            rrfracr0_temp = [rrfracr0_ER11(ii_ER11) rrfracr0_E04(ii_E04)];
            MMfracM0_temp = [MMfracM0_ER11(ii_ER11) MMfracM0_E04(ii_E04)];
            clear ii_ER11 ii_E04

            %% Check to see how close solution is to input value of (rfitr0,MfitM0)
            rfitr0 = rfit/r0;
            MfitM0 = Mfit/M0;

            %% Updated 2020-06-23 -- fixed problem that code returned NaN (--> incorrect final solution) if true rfit > current r0
            if(rfitr0<=1)
                MfitM0_temp = interp1(rrfracr0_temp,MMfracM0_temp,rfitr0,'pchip',NaN);

                MfitM0_err = MfitM0 - MfitM0_temp;
            else %the true rfit is larger than the current r0, which means it doesn't exist in the profile!
                    %need a smaller r0 -- just set MfitM0_err to a large positive number
                MfitM0_err = 10^6;  
            end

            if(MfitM0_err>0)    %need smaller rmax (r0)
                drmaxrfit = abs(drmaxrfit)/2;
            else    %need larger rmax (r0)
                drmaxrfit = -abs(drmaxrfit)/2;
            end

        else    %ER11_radprof did not converge -- convergence fails for low CkCd and high Ro = Vm/(f*rm)

            %%Must reduce rmax (and thus reduce Ro)
            drmaxrfit = -abs(drmaxrfit)/2;

        end

        %%update value of rmaxrfit
        rmaxrfit = rmaxrfit_new;    %this is the final one
        rmaxrfit_new = rmaxrfit + drmaxrfit;

        %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        %%TESTING: Plot radial profile, mark rrad, and plot E04 model fits and rmaxs %%%%%%
        %{
        figure(1011)
        plot(rrfracr0_temp,MMfracM0_temp,'b')
        hold on
        plot(rfitr0,MfitM0,'r.','MarkerSize',40)
        plot(rmaxr0,MmM0,'bx')
        axis([0 1 0 1])
        xlabel('r/r_0');
        ylabel('M/M_0');
        'hi'
        %}
        %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


    end
    
    %%Check if solution converged
    if(~isnan(max(VV_ER11)))
        soln_converged = 1;
    else
        soln_converged = 0;
        CkCd = CkCd + .1;
        sprintf('Adjusting CkCd to find convergence')
    end
    
end

%% Finally: Interpolate to a grid
% drfracr0 = .0001;
% rfracr0_min = 0;    %[-]; r=0
% rfracr0_max = 1;   %[-]; r=r0
% rrfracr0 = rfracr0_min:drfracr0:rfracr0_max; %[]; r/r0 vector
% MMfracM0 = interp1(rrfracr0_temp,MMfracM0_temp,rrfracr0,'pchip',NaN);
drfracrm = .01; %calculating VV at radii relative to rmax ensures no smoothing near rmax!
rfracrm_min = 0;    %[-]; r=0
rfracrm_max = r0/rmax;   %[-]; r=r0
rrfracrm = rfracrm_min:drfracrm:rfracrm_max+drfracrm; %[]; r/r0 vector
MMfracMm = interp1(rrfracr0_temp*(r0/rmax),MMfracM0_temp*(M0/Mm),rrfracrm,'pchip');

rrfracr0 = rrfracrm*rmax/r0;    %save this as output
MMfracM0 = MMfracMm*Mm/M0;

%% Calculate dimensional wind speed and radii
% VV = (M0/r0)*((MMfracM0./rrfracr0)-rrfracr0);  %[ms-1]
% rr = rrfracr0*r0;   %[m]
% rmerge = rmerger0*r0;
% Vmerge = (M0/r0)*((MmergeM0./rmerger0)-rmerger0);  %[ms-1]
VV = (Mm/rmax)*(MMfracMm./rrfracrm)-.5*fcor*rmax*rrfracrm;  %[ms-1]
rr = rrfracrm*rmax;   %[m]

%% Make sure V=0 at r=0
VV(rr==0) = 0;

rmerge = rmerger0*r0;
Vmerge = (M0/r0)*((MmergeM0./rmerger0)-rmerger0);  %[ms-1]

%% Adjust profile in eye, if desired
if(eye_adj==1)
    r_eye_outer = rmax;
    V_eye_outer = Vmax;
    [VV] = radprof_eyeadj(rr,VV,alpha_eye,r_eye_outer,V_eye_outer);

%    sprintf('EYE ADJUSTMENT: eye alpha = %3.2f',alpha_eye)
end

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%TESTING: Plot radial profile, mark rrad, and plot E04 model fits and rmaxs %%%%%%
%{
figure(1009)
plot(rrfracr0,MMfracM0,'b')
hold on
plot(rmerger0,MmergeM0,'rx')
plot(rmaxr0,MmM0,'rx')
axis([0 1 0 1])
xlabel('r/r_0');
ylabel('M/M_0');

figure(1010)
plot(rr/1000,VV,'b')
hold on
plot(rmerge/1000,Vmerge,'rx')
plot(rmax/1000,Vmax,'rx')
xlabel('r [km]');
ylabel('V [m/s]');
%}
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

end

%------------- END OF CODE --------------