/*  Example of wrapping cos function from math.h with the Python-C-API. */

#include <Python.h>
#include <math.h>

static PyObject *method_fputs(PyObject *self, PyObject *args) {
    char *str, *filename = NULL;
    int bytes_copied = -1;

    /* Parse arguments */
    if(!PyArg_ParseTuple(args, "ss", &str, &filename)) {
        return NULL;
    }

    FILE *fp = fopen(filename, "w");
    bytes_copied = fputs(str, fp);
    fclose(fp);

    return PyLong_FromLong(bytes_copied);
};


static PyObject *integrate_spmodel_wrapper(PyObject *self, PyObject *args) {
    /* Parse arguments */
    char *str, *filename = NULL;
    int bytes_copied = -1;
    
    if(!PyArg_ParseTuple(args, "ss", &str, &filename)) {
        return NULL;
    }

    FILE *fp = fopen(filename, "w");
    bytes_copied = fputs(str, fp);
    fclose(fp);


    return PyLong_FromLong(bytes_copied);
}

static PyMethodDef FastClockMethods[] = {
    {"fputs", method_fputs, METH_VARARGS, "Python interface for fputs C library function"},
    {"integrate_spmodel", integrate_spmodel_wrapper, METH_VARARGS, "integrate the single pop model using RK4"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef fastclockmodule = {
    PyModuleDef_HEAD_INIT,
    "fastclock",
    "Python interface for the fastclocks C library functions",
    -1,
    FastClockMethods
};


PyMODINIT_FUNC PyInit_fastclock(void) {
    return PyModule_Create(&fastclockmodule);
}