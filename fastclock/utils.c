
#include "utils.h"

double sum_array(double *hr, int n)
{
    double sum = 0.0;
    for (int k = 0; k < n; k++)
    {
        sum += hr[k];
    }
    return sum;
}

void add_states(double *result, double *state_mod, double *state2, double scalar, int dim)
{
    // overwrites the first array a=b+scalar*c

    for (int i = 0; i < dim; i = i + 1)
    {
        result[i] = state_mod[i] + scalar * state2[i];
    }
}

double rand_normal(double mean, double stddev)
{//Box muller method
    static double n2 = 0.0;
    static int n2_cached = 0;
    if (!n2_cached)
    {
        double x, y, r;
        do
        {
            x = 2.0*rand()/RAND_MAX - 1;
            y = 2.0*rand()/RAND_MAX - 1;

            r = x*x + y*y;
        }
        while (r == 0.0 || r > 1.0);
        {
            double d = sqrt(-2.0*log(r)/r);
            double n1 = x*d;
            n2 = y*d;
            double result = n1*stddev + mean;
            n2_cached = 1;
            return result;
        }
    }
    else
    {
        n2_cached = 0;
        return n2*stddev + mean;
    }
}
