import { useMutation, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import useAuthContext from "./AuthContext";
import Svg from "./Svg";
import PropTypes from "prop-types";

Save.propTypes = {
  postId: PropTypes.number,
  initialSaved: PropTypes.bool,
};

export default function Save({ postId, initialSaved = false }) {
  const [saved, setSaved] = useState(initialSaved);
  const { isAuthenticated } = useAuthContext();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();

  useEffect(() => {
    setSaved(initialSaved);
  }, [initialSaved]);

  const { mutate, isPending } = useMutation({
    mutationFn: async ({ saved }) => {
      if (saved) {
        return axios.put(`/api/posts/saved/${postId}`).then((res) => res.data);
      } else {
        return axios
          .delete(`/api/posts/saved/${postId}`)
          .then((res) => res.data);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["posts"] });
      queryClient.invalidateQueries({ queryKey: ["post/comment"] });
    },
  });

  function handleSave() {
    if (!isAuthenticated) {
      const returnUrl = location.pathname + location.search;
      navigate(
        `/login?redirect=${encodeURIComponent(returnUrl)}&savePost=${postId}`,
      );
      return;
    }
    const newSaved = !saved;
    setSaved(newSaved);
    mutate({ saved: newSaved });
  }

  return (
    <div
      className={`flex items-center space-x-2 md:cursor-pointer group ${isPending ? "opacity-50 pointer-events-none" : ""}`}
      onClick={handleSave}
    >
      <Svg
        type="save"
        className="w-4 h-4 md:w-5 md:h-5"
        active={saved}
        defaultStyle={true}
      />
      <p className="text-sm md:text-base">
        {isPending ? "..." : saved ? "Saved" : "Save"}
      </p>
    </div>
  );
}
