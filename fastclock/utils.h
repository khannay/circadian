#ifndef UTILS_HEADER
#define UTILS_HEADER

#include <stdlib.h> 
#include <math.h>

double sum_array(double *hr, int n);
void add_states(double *result, double *state_mod, double *state2, double scalar, int dim);
double rand_normal(double mean, double stddev);

#endif