#ifndef RK4_HEADER
#define RK4_HEADER

#include <stdlib.h>
#include <math.h>
#include "utils.h"

void rk4( double* func(double*, double, double*),
double *ustart, double light_val, double dt, double *params, int dim);


#endif