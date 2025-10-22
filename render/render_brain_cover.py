# render_brain_cover.py
import sys, argparse
import slicer
import ScreenCapture
import ScreenCapture, os, subprocess, shutil
_tmp3d_widget = None  # keep a reference in headless mode


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--volume", required=True)
    p.add_argument("--labels", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--preset", default="DTI-FA-Brain")
    p.add_argument("--opacity", type=float, default=0.35)
    return p.parse_args(argv)

def get_three_d_view():
    lm = slicer.app.layoutManager()
    if lm:  # GUI mode
        return lm.threeDWidget(0).threeDView()
    # Headless: create our own widget + view
    global _tmp3d_widget
    _tmp3d_widget = slicer.qMRMLThreeDWidget()
    _tmp3d_widget.setMRMLScene(slicer.mrmlScene)
    _tmp3d_widget.resize(1280, 960)
    _tmp3d_widget.show()
    slicer.app.processEvents()
    return _tmp3d_widget.threeDView()

def load_volume(path):
    node = slicer.util.loadVolume(path)
    if not node: raise RuntimeError(f"Failed to load volume: {path}")
    return node

def load_labels_as_seg(path, ref):
    label = slicer.util.loadLabelVolume(path)
    if not label: raise RuntimeError(f"Failed to load labelmap: {path}")
    seg = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", "Segmentation")
    slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(label, seg)
    seg.SetReferenceImageGeometryParameterFromVolumeNode(ref)
    return seg

def enable_vr(volumeNode, preset):
    vrLogic = slicer.modules.volumerendering.logic()

    # Create (or reuse) VR display nodes for this volume
    displayNode = vrLogic.CreateDefaultVolumeRenderingNodes(volumeNode)

    # Make sure we have an ROI *for this display node*
    roiNode = displayNode.GetROINode()
    if roiNode is None:
        roiNode = vrLogic.CreateROINode(displayNode)
        displayNode.SetAndObserveROINodeID(roiNode.GetID())

    # Fit ROI to the volume (API expects DISPLAY NODE)
    vrLogic.FitROIToVolume(displayNode)

    # Apply preset (or use Slicer's heuristic recommender)
    presetNode = vrLogic.GetPresetByName(preset)
    if presetNode:
        displayNode.GetVolumePropertyNode().Copy(presetNode)
    else:
        vrLogic.SetRecommendedVolumeRenderingProperties(displayNode)

    # Disable cropping visuals and show VR
    displayNode.SetCroppingEnabled(False)
    if roiNode and roiNode.GetDisplayNode():
        roiNode.GetDisplayNode().SetVisibility(False)

    displayNode.SetVisibility(True)
    return displayNode

def show_segments_3d(segNode, opacity=0.35):
    # Create smooth closed surfaces
    segNode.CreateClosedSurfaceRepresentation()
    disp = segNode.GetDisplayNode()
    disp.SetOpacity3D(opacity)
    disp.SetVisibility3D(True)

def setup_view():
    view = get_three_d_view()
    vn = view.mrmlViewNode()

    # Clean frame
    vn.SetBoxVisible(False)
    vn.SetAxisLabelsVisible(False)
    vn.SetRulerType(0)  # 0=None, hides corner rulers if any

    # Background (optional)
    vn.SetBackgroundColor(0.14, 0.14, 0.20)
    vn.SetBackgroundColor2(0.14, 0.14, 0.20)

    # Center camera
    view.resetFocalPoint()
    slicer.app.processEvents()

    # Zoom out a touch (FOV is a single float in degrees)
    try:
        fov = vn.GetFieldOfView()
        # If some builds ever return a tuple, handle both:
        if isinstance(fov, (tuple, list)):
            vn.SetFieldOfView(fov[0] * 1.25)
        else:
            vn.SetFieldOfView(float(fov) * 1.25)
    except Exception:
        pass

    return view

def capture_png(path, scale=4):
    view = get_three_d_view()
    cap = ScreenCapture.ScreenCaptureLogic()
    slicer.app.processEvents()
    cap.captureImageFromView(view, path, scale)

def capture_spin_gif(out_basename: str, n_frames=61, fps=30, make_gif=True):
    """
    Saves a 360° spin as:
      - PNG sequence: f"{out_basename}_%04d.png"
      - (optional) MP4: f"{out_basename}.mp4" if ffmpeg is configured
      - (optional) GIF:  f"{out_basename}.gif" via system ffmpeg (post-step)
    """
    import ScreenCapture, os, subprocess, shutil
    cap = ScreenCapture.ScreenCaptureLogic()
    view = get_three_d_view()  # from your script
    viewNode = view.mrmlViewNode()

    # Set up a spin: yaw around vertical axis
    # ScreenCapture module exposes high-level helpers via the GUI, but in script
    # we rotate the camera incrementally and capture each frame.
    renderer = view.renderWindow().GetRenderers().GetItemAsObject(0)
    camera = renderer.GetActiveCamera()

    # Reset, slight zoom-out already done in setup_view()
    view.resetFocalPoint()
    slicer.app.processEvents()

    import math
    out_dir = os.path.dirname(out_basename)
    os.makedirs(out_dir, exist_ok=True)

    for i in range(n_frames):
        angle_deg = 360.0 * i / n_frames
        camera.Azimuth(360.0 / n_frames)  # yaw step
        view.renderWindow().Render()
        slicer.app.processEvents()
        cap.captureImageFromView(view, f"{out_basename}_{i:04d}.png", 1)

    # Optional MP4 directly from ScreenCapture (if ffmpeg path set in Slicer prefs)
    # You can also omit this and always do ffmpeg externally.
    try:
        cap.captureVideoFromView(view, f"{out_basename}.mp4", fps, n_frames)
    except Exception:
        pass

    # Optional: make a high-quality GIF via system ffmpeg if available
    if make_gif and shutil.which("ffmpeg"):
        palette = f"{out_basename}_palette.png"
        seq = f"{out_basename}_%04d.png"
        # palette + use (best practice for smooth GIFs)
        subprocess.run(["ffmpeg","-y","-framerate",str(fps),"-i",seq,"-vf","palettegen",palette], check=False)
        subprocess.run(["ffmpeg","-y","-framerate",str(fps),"-i",seq,"-i",palette,"-lavfi","paletteuse",
                        f"{out_basename}.gif"], check=False)


def main(argv):
    a = parse_args(argv)
    vol = load_volume(a.volume)
    seg = load_labels_as_seg(a.labels, vol)
    setup_view()
    enable_vr(vol, a.preset)
    show_segments_3d(seg, a.opacity)
    get_three_d_view().resetFocalPoint()

    capture_png(a.out, scale=4)
    spin_base = os.path.splitext(a.out)[0]  # reuse same name prefix
    capture_spin_gif(spin_base, n_frames=61, fps=30, make_gif=True)

    print(f"[OK] Saved: {a.out}")

if __name__ == "__main__":
    user_argv = sys.argv[1:]
    main(user_argv)
    slicer.util.exit()

