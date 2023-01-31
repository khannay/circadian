#ifndef SPMODEL_HEADER
#define SPMODEL_HEADER

#include <math.h>
#include <stdlib.h>
#include "utils.h"
#include "rk4.h"

double *spmodel(double *u, double light, double *params);
void integrate_spmodel(double *u0, double *ts, double *light_est, double *params, int n);
void integrate_spmodel_save(double sol[][3], double *u0, double *ts, double *light_est, double *params, int n);

#endif
