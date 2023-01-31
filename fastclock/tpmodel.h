#ifndef SPMODEL_HEADER
#define SPMODEL_HEADER

#include <math.h>
#include <stdlib.h>
#include "utils.h"
#include "rk4.h"

double *tpmodel(double *u, double light, double *params);
void integrate_tpmodel(double *u0, double *ts, double *light_est, double *params, int n);
void integrate_tpmodel_save(double sol[][5], double *u0, double *ts, double *light_est, double *params, int n);

#endif