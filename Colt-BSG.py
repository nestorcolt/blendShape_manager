import maya.cmds as cmds
import pymel.core as pm
import maya.OpenMaya as om
import random
import re
import collections

###################################################################################################
# Globals:


def undo(func):
    def wrapper(*args, **kwargs):
        cmds.undoInfo(openChunk=True)
        try:
            ret = func(*args, **kwargs)
        finally:
            cmds.undoInfo(closeChunk=True)
        return ret
    return wrapper
###################################################################################################


class Extract_blendShapes(object):
    """docstring for Extract_blendShapes"""

    def __init__(self, debug=False):
        super(Extract_blendShapes, self).__init__()
        # publicMembers:
        #
        self.sourceObject = None
        self.targetObject = None
        self.sourceNode = None
        self.targetNode = 'TargetBlendShape'
        self.targetValues = {}
        self.connections = {}
        self.new_blendshape_node = None

        self.weights = []
        self.targets = []
        #
        self.toConnect = False
        self.mainGroup = 'sculptedTargets_Colt'
        self.debug = debug

    ###################################################################################################
    # get meshes
    #
    def get_geos(self):
        selected = pm.ls(sl=True)

        if len(selected) < 1:
            pm.warning('Please Select an object on scene')
            return

        return selected

    ###################################################################################################
    # this gets the real targets from the input target Group, because sometimes the bs node stores ghost weights hidden inside the node an call them Weight[X]
    #
    def get_real_targets_lenght(self, node):
        inputTargets = cmds.ls(node + ".inputTarget[0].inputTargetGroup[*]")

        """
        array = []

        for targ in inputTargets:
            index = re.compile(r'\d+')
            index = index.findall(targ)[-1]
            array.append(int(index))

        # return max(array)"""

        return len(inputTargets)

    ###################################################################################################
    # get connections from each target in source bs node
    #
    def get_connections(self):

        connecctions = collections.defaultdict(dict)

        for trg in cmds.listAttr(self.sourceNode + '.w', m=True):
            trg = self.sourceNode + '.' + trg
            inputCon = cmds.listConnections(trg, scn=True, p=True)

            if inputCon is not None:
                inputCon.reverse()

                try:
                    connecctions[trg]['input'] = inputCon[0]
                    connecctions[trg]['output'] = inputCon[-1]

                except ValueError:
                    pass
        #
        self.connections = connecctions

    ###################################################################################################
    # reconnect targets in new bs node
    #
    def reconnect_targets(self):

        if self.debug:
            self.new_blendshape_node = 'tester_node_1155'

        for trg, connect in self.connections.items():
            spl_targ = trg.split('.')[-1]
            newTarget = self.new_blendshape_node + '.' + spl_targ

            if self.debug:
                print('Connection from: %s    to: %s' %
                      (connect['input'], newTarget))
                print('Connection from: %s    to: %s' %
                      (newTarget, connect['output']))

            #
            else:
                try:

                    cmds.connectAttr(connect['input'], newTarget, f=True)
                    cmds.connectAttr(newTarget, connect['output'], f=True)

                except ValueError:
                    pass

        # re activate live targets if they are not blocked or connected
        #
        for attr in self.weights:
            if cmds.getAttr(self.new_blendshape_node + '.' + attr, se=True):
                cmds.setAttr(self.new_blendshape_node + '.' + attr, 1)
                cmds.setAttr(self.new_blendshape_node + '.' + attr, lock=True)

    ###################################################################################################
    # get data to handle over the object
    #

    def getData(self, geometry):
        """

            Description: gets the data from the bs node {each target with inbetween and values}
            Return: Dict / Array with key: target index, value: array with Target weights - source BS node - weight list

        """

        sourceObject = geometry

        shape = pm.listRelatives(sourceObject, s=True)[0]
        blendShapeSource = [itm for itm in pm.listHistory(
            shape) if pm.objectType(itm, isType='blendShape')]

        if len(blendShapeSource) == 0:
            cmds.warning('No BlendShape Node Found in Object Source')
            return

        sourceNode = blendShapeSource[0]

        #
        weights = self.get_real_targets_lenght(sourceNode)
        #
        final_targets = {}

        for idx in range(weights):
            elements = pm.ls('{}.inputTarget[0].inputTargetGroup[{}].inputTargetItem[*]'.format(sourceNode, idx))
            weightValues_perElement = []

            for itm in elements:
                intValue = itm.split('.')[-1][-5:-1]
                weight = float(int(intValue) - 5000) / 1000
                weightValues_perElement.append(weight)

            #
            #
            if len(elements) > 0:
                ordered_values = sorted(weightValues_perElement, reverse=True)
                final_targets[idx] = [ordered_values[0], ordered_values[1:]]

        return final_targets, sourceNode, weights

    ###################################################################################################
    # find and merge the live target no matter is the name was changed inside the bs node or in the outliner object
    #

    def merge_live_targets(self, weightCount, sourceNode):
        #
        nodeData = cmds.listAttr(sourceNode + '.w', m=True)

        # init generic counter
        counter = 0

        for idx in range(weightCount):
            elements = cmds.ls('{}.inputTarget[0].inputTargetGroup[{}].inputTargetItem[*]'.format(sourceNode, idx))

            if len(elements) > 0:
                conPort = cmds.listConnections('{}.inputTarget[0].inputTargetGroup[{}].inputTargetItem[6000].inputGeomTarget'.format(sourceNode, idx))

                if conPort is not None:
                    nodeData[counter] = conPort[0]

                # raise generic counter
                counter += 1

        return nodeData

    ###################################################################################################
    # rebuild the targets available in the blendshape node
    #

    @undo
    def rebuild_BS(self, main_index, bsNode='', inBetArray=[]):

        BS_targets = {}
        inBetweens = []
        to_parent = []

        target = pm.sculptTarget(
            bsNode, target=main_index, edit=True, regenerate=True)

        if target is not None:
            py_targ = pm.PyNode(target[0])
            pm.addAttr(py_targ, ln='value', at='float', defaultValue=1.000)
            to_parent.append(py_targ)

            if len(inBetArray) > 0:
                for value in inBetArray:
                    inBet = pm.sculptTarget(
                        bsNode, target=main_index, edit=True, regenerate=True, ibw=value)
                    py_inBet = pm.PyNode(inBet[0])
                    newInBet = pm.rename(py_inBet, str(
                        py_targ.name() + '_InBet_%s' % ''.join(str(value).split('.'))))
                    inBetweens.append([newInBet, value])
                    to_parent.append(py_inBet)
                    self.tag_for_inbetween(py_targ, py_inBet, value)
                    # print(py_inBet)

            #
            BS_targets[py_targ] = inBetweens

            # parent to main group
            pm.parent(to_parent, self.mainGroup)

        return

    ###################################################################################################
    # gets the data and feed the object properties
    #
    def feedObjWithData(self, geos=[]):
        """

            Description: Prioritize if get geos as argument, if not call method get_geos from selection

        """

        if len(geos) == 0:

            geometries = self.get_geos()

            if geometries:
                self.sourceObject = geometries[0]

                if len(geometries) == 2:
                    self.targetObject = geometries[1]

        else:
            self.sourceObject = geos[0]
            self.targetObject = geos[1]

        targets, bs_node, weightList = self.getData(self.sourceObject)

        if not self.debug:
            if self.targetObject:
                # creates the main group on init
                pm.createNode('transform', n=self.mainGroup)

        self.sourceNode = bs_node
        self.targets = weightList
        self.targetValues = targets
        self.weights = self.merge_live_targets(self.get_real_targets_lenght(self.sourceNode), self.sourceNode)

    ###################################################################################################
    # tag inbetween if available, and stablish a relationship between the main target and this inbet target
    #
    def tag_for_inbetween(self, parent, child, value=''):

        if not pm.attributeQuery('parent', node=parent, exists=True):
            pm.addAttr(parent, ln='parent', at='message')

        # att att message to inbetween
        pm.addAttr(child, ln='child', at='message')
        pm.addAttr(child, ln='value', at='float', defaultValue=0.000)
        pm.connectAttr(parent + '.parent', child + '.child', f=True)
        child.attr('value').set(value)

        return True

    ###################################################################################################
    # migrate the data stored in a bs node to a new one in a diferent or same mesh
    #

    def migrate(self, weights, new_mesh=''):

        if not new_mesh:
            om.MGlobal.displayError("No target mesh found in selection")
            return

        # new blend shape name
        new_BS_node = self.targetNode + '_' + \
            str(random.randint(4145, 1514545442))
        self.new_blendshape_node = new_BS_node

        # create BS node
        pm.blendShape(new_mesh, n=new_BS_node, foc=True)

        for idx, item in enumerate(weights):
            newTarg = item

            #
            pm.blendShape(new_BS_node, edit=True, t=(
                new_mesh, idx, str(newTarg), 1.0))

            if pm.attributeQuery('parent', node=newTarg, exists=True):
                downstreamNodes = pm.listConnections(
                    '{}.{}'.format(newTarg, 'parent'), d=True)

                for inBet in downstreamNodes:
                    val = float('%.3f' % pm.getAttr(inBet + '.value'))
                    pm.blendShape(new_BS_node, edit=True, t=(
                        new_mesh, idx, inBet, float(val)))


###################################################################################################

###################################################################################################
# builder function
#
@undo
def builder(migrate=False, mirror=False, debug=False):
    instance = Extract_blendShapes(debug=debug)
    instance.feedObjWithData()

    if not debug:

        if instance.targetObject:
            # re - sculpt targets
            for key, val in instance.targetValues.items():
                instance.rebuild_BS(bsNode=instance.sourceNode,
                                    inBetArray=val[1], main_index=key)

            if migrate:
                # migrate bs from node
                instance.migrate(instance.weights, instance.targetObject)
                instance.get_connections()
                instance.reconnect_targets()

            # delete parent main group
            if pm.objExists(instance.mainGroup):
                pm.delete(instance.mainGroup)

    else:
        instance.get_connections()
        instance.reconnect_targets()


###################################################################################################
#
if __name__ == '__main__':
    builder(migrate=True, debug=False)
    pass
