
#include "rk4.h"




void rk4( double* func(double*, double, double*),
double *ustart, double light_val, double dt, double *params, int dim) {

    double *u0 = (double *)malloc(sizeof(double) * dim);

    double *k1 = func(ustart, light_val, params);
    add_states(u0, ustart, k1, dt / 2.0, dim);
    double *k2 = func(u0, light_val, params);
    add_states(u0, ustart, k2, dt / 2.0, dim);
    double *k3 = func(u0, light_val, params);
    add_states(u0, ustart, k3, dt, dim);
    double *k4 = func(u0, light_val, params);

    for (int i = 0; i < dim; i = i + 1)
    {
        ustart[i] = ustart[i] + dt / 6.0 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]);
    }
    free(u0);
    free(k1);
    free(k2);
    free(k3);
    free(k4);
}