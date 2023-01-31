

#include "tpmodel.h"
#include "utils.h"

double* tpmodel(double *u, double light, double *params)
{

    double *du = (double *)malloc(sizeof(double) * 5);

    double Rv = u[0];
    double Psi_v = u[1];
    double Rd = u[1];
    double Psi_d = u[2];
    double n = u[0];

    const double tau = params[0];
    const double K = params[1];
    const double gamma = params[2];
    const double Beta1 = params[3];
    const double A1 = params[4];
    const double A2 = params[5];
    const double BetaL1 = params[6];
    const double BetaL2 = params[7];
    const double sigma = params[8];

    // Process L parameters
    const double G = params[9];
    const double alpha_0 = params[10];
    const double delta = params[11];
    const double I_0 = params[12];
    const double p = params[13];

    const double alpha_L = alpha_0 * (pow(light, p)) / (pow(light, p) + I_0);
    const double Bhat = G * (1 - n) * alpha_L;

    double LightAmp = A1 * 0.5 * Bhat * (1.0 - pow(R, 4.0)) * cos(Psi + BetaL1) + A2 * 0.5 * Bhat * R * (1.0 - pow(R, 8.0)) * cos(2.0 * Psi + BetaL2);
    double LightPhase = sigma * Bhat - A1 * Bhat * 0.5 * (pow(R, 3.0) + 1.0 / R) * sin(Psi + BetaL1) - A2 * Bhat * 0.5 * (1.0 + pow(R, 8.0)) * sin(2.0 * Psi + BetaL2);

    du[0] = -1.0 * gamma * R + K * cos(Beta1) / 2.0 * R * (1.0 - pow(R, 4.0)) + LightAmp;
    du[1] = 2 * M_PI / tau + K / 2.0 * sin(Beta1) * (1 + pow(R, 4.0)) + LightPhase;
    du[2] = 60.0 * (alpha_L * (1 - n) - delta * n);

    return du;
}

void integrate_tpmodel(double *u0, double *ts, double *light_est, double *params, int n)
{

    // Integrate the spmodel forward in time using the given light estimate vector
    //overwrites u0 with the new state

    double dt;
    double* (*func)(double*, double, double*);
    func=&tpmodel;

    for (int k = 0; k < n - 1; k = k + 1)
    {
        dt = ts[k + 1] - ts[k];
        rk4(func, u0, light_est[k], dt, params,3);

        //spmodel_rk4_step(u0, light_est[k], dt, params);
    }
}

void integrate_spmodel_save(double sol[][3], double *u0, double *ts, double *light_est, double *params, int n)
{

    // Integrate the spmodel forward in time using the given light estimate vector
    //overwrites the first argument with the values

    double dt;
    double* (*func)(double*, double, double*);
    func=&spmodel;

    for (int j = 0; j < 3; j++) { sol[0][j] = u0[j]; }
    for (int k = 0; k < n - 1; k = k + 1)
    {
        dt = ts[k + 1] - ts[k];
        rk4(func, u0, light_est[k], dt, params,3);
        for (int j = 0; j < 5; j++)
        {
            sol[k + 1][j] = u0[j];
        }
    }
}