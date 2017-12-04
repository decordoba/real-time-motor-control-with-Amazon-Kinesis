import matplotlib.pyplot as plt


# Enable interactive mode
def plt_ion():
    plt.ion()


# Disable interactive mode
def plt_ioff():
    plt.ioff()


# Plot a line or point cloud. Also accepts several lines at the same time, if you set y_pts and
# x_pts as lists of lists.
# @use transformCurvesToPlot([[-2,2],[-2,-1,0,1,2],[0,0]], [[0,0],[-2,-1,0,1,2],[-2,2]])
def plotLine(y_pts, x_pts=None, y_label=None, x_label=None, title=None, axis=None, style="-",
             color="", y_scale="linear", x_scale="linear", label=None, show=True, figure=0,
             filename=None):
    """
    :param y_pts: y coordinates. A list of list can represent several lines
    :param x_pts: x coordinates. A list of list can represent several lines
    :param y_label: label for y axis
    :param x_label: label for x axis
    :param title: the title of the figure
    :param axis: len4 list [xmin, xmax, ymin, ymax] to pick range we will see
    :param style: ('-': line), ('x': cross), ('o': circle), ('s': squre), ('--': dotted line)...
    :param color: 'r','g','b','c','m','y','k'... If left blank, every curve will take a new color
    :param label: text that will be displayed if we show a legend
    :param show: whether to show result or not. Show is blocking (pauses the execution) until the
                 plot window is closed
    :param figure: figure number used
    """
    plt.figure(figure)
    if x_pts is None:
        plt.plot(y_pts, color + style, label=label)
    else:
        if isinstance(y_pts, list) and isinstance(y_pts[0], list):
            (y_pts, x_pts) = transformCurvesToPlot(y_pts, x_pts)
        plt.plot(x_pts, y_pts, color + style, label=label)
    if y_label is not None:
        plt.ylabel(y_label)
    if x_label is not None:
        plt.xlabel(x_label)
    if title is not None:
        plt.title(title)
        figname = title.replace(" ", "_") + ".png"
    else:
        figname = str(figure) + ".png"
    if filename is not None:
        figname = filename + ".png"
    if axis is not None:
        plt.axis(axis)
    plt.yscale(y_scale)
    plt.xscale(x_scale)
    plt.draw()
    if show:
        plt.show()
    plt.savefig("figures/{}".format(figname))


# pyplot can print more than one curve at the same time, but it doesn't do it in an intuitive way.
# transformCurvesToPlot gets a list of  curves y_pts = [[curveA_y], [curveB_y], [curveC_y]] and
# x_pts = [[curveA_x], [curveB_x], [curveC_x]] and returns a tuple like:
# ([[curveA_y0, curveB_y0, curveC_y0], [curveA_y1, curveB_y1, curveC_y1]...]],
# [curveA_x0, curveB_x0, curveC_x0], [curveA_x1, curveB_x1, curveC_x1]...])
# It accepts curves of different lengths too. The new y_pts and x_pts will plot all curves ok.
# @use transformCurvesToPlot([[-2,2],[-2,-1,0,1,2],[0,0]], [[0,0],[-2,-1,0,1,2],[-2,2]])
def transformCurvesToPlot(y_pts, x_pts):
    new_y_pts = []
    new_x_pts = []
    last_row = max([len(row) for row in y_pts])
    for i, row in enumerate(y_pts):
        for j, y in enumerate(row):
            try:
                new_y_pts[j].append(y)
                new_x_pts[j].append(x_pts[i][j])
            except IndexError:
                new_y_pts.append([y])
                new_x_pts.append([x_pts[i][j]])
        x = x_pts[i][j]
        while j < last_row:
            j += 1
            try:
                new_y_pts[j].append(y)
                new_x_pts[j].append(x)
            except IndexError:
                new_y_pts.append([y])
                new_x_pts.append([x])
    return (new_y_pts, new_x_pts)


def plotPlotBox(y_pts, y_label=None, x_label=None, title=None, axis=None, label=None, show=True,
                figure=0, filename=None):
    plt.figure(figure)
    plt.boxplot(y_pts)
    if y_label is not None:
        plt.ylabel(y_label)
    if x_label is not None:
        plt.xlabel(x_label)
    if title is not None:
        plt.title(title)
        figname = title.replace(" ", "_") + ".png"
    else:
        figname = str(figure) + ".png"
    if filename is not None:
        figname = filename + ".png"
    if axis is not None:
        plt.axis(axis)
    plt.draw()
    if show:
        plt.show()
    plt.savefig("figures/{}".format(figname))
